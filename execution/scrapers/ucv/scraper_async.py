
import asyncio
import aiohttp
import logging
import time
import socket
import os
from typing import Dict, List, Optional
from pathlib import Path
from asyncio import Semaphore
import yaml
from datetime import datetime

# Setup logging
logger = logging.getLogger("async_scraper")

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED" # CLOSED, OPEN

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit Breaker TRIPPED! failures={self.failures}")

    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"

    def is_open(self):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "CLOSED" # Half-open/Reset
                self.failures = 0
                return False
            return True
        return False

class DomainAwareScraper:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.base_dir = Path("data/runs") / run_id / "raw"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Load Config
        with open("execution/scrapers/ucv/config.yaml", "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
            
        settings = self.config.get("async_settings", {})
        self.groups_config = settings.get("domain_groups", {})
        
        # Initialize Semaphores & Circuit Breakers per group
        self.semaphores = {}
        self.breakers = {}
        
        for group_name, cfg in self.groups_config.items():
            self.semaphores[group_name] = Semaphore(cfg.get("max_concurrent", 2))
            self.breakers[group_name] = CircuitBreaker(
                failure_threshold=settings.get("circuit_breaker", {}).get("failure_threshold", 3),
                reset_timeout=settings.get("circuit_breaker", {}).get("reset_timeout", 300)
            )
            
        # Fallback for unknown domains
        self.semaphores["default"] = Semaphore(2)
        self.breakers["default"] = CircuitBreaker()

    def _get_domain_group(self, url: str) -> str:
        for group_name, cfg in self.groups_config.items():
            for domain in cfg.get("domains", []):
                if domain in url:
                    return group_name
        return "ucv_subdomains" if ".ucv.ro" in url else "ucv_main"

    async def run_async(self, test_limit: int = 0):
        faculties = self.config.get("faculties", [])
        if test_limit > 0:
            faculties = faculties[:test_limit]
            
        # Force IPv4 to avoid getaddrinfo errors on some envs
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            for faculty in faculties:
                tasks.append(self._process_faculty(session, faculty))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            self._summarize_results(results)

    async def _process_faculty(self, session: aiohttp.ClientSession, faculty: Dict):
        slug = faculty["slug"]
        urls = faculty.get("urls", [])
        if not urls and "url" in faculty:
            urls = [faculty["url"]]
            
        results = []
        for url in urls:
            domain_group = self._get_domain_group(url)
            breaker = self.breakers.get(domain_group, self.breakers["default"])
            sem = self.semaphores.get(domain_group, self.semaphores["default"])
            
            if breaker.is_open():
                logger.warning(f"[{slug}] Skipped {url} (Circuit Breaker OPEN)")
                results.append("SKIPPED_CB")
                continue

            async with sem:
                success = False
                for attempt in range(2): # Retry once
                    try:
                        logger.info(f"[{slug}] Fetching {url} (Attempt {attempt+1})...")
                        ts_start = time.time()
                        # Use specific limits for fragile servers
                        timeout = aiohttp.ClientTimeout(total=45, connect=10)
                        
                        async with session.get(url, timeout=timeout, ssl=False) as resp:
                            if resp.status != 200:
                                logger.error(f"[{slug}] HTTP {resp.status} for {url}")
                                # Only count 5xx as breaker failures, 4xx are just errors
                                if 500 <= resp.status < 600:
                                     breaker.record_failure()
                                results.append(f"HTTP_{resp.status}")
                                break # Stop retrying on HTTP error response
                                
                            html = await resp.text(errors='replace') # robust decoding
                            duration = time.time() - ts_start
                            breaker.record_success()
                            
                            # Save Snapshot
                            self._save_snapshot(slug, html, url)
                            logger.info(f"[{slug}] Success {url} ({duration:.2f}s)")
                            results.append("OK")
                            success = True
                            break
                            
                    except Exception as e:
                        logger.warning(f"[{slug}] Error {url} (Attempt {attempt+1}): {str(e)}")
                        await asyncio.sleep(1) # Backoff
                
                if not success:
                    breaker.record_failure()
                    results.append("ERROR")
                    
        return {slug: results}

    def _save_snapshot(self, slug: str, html: str, url: str):
        path = self.base_dir / slug / "snapshot.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"<!-- Source: {url} -->\n")
            f.write(html)

    def _summarize_results(self, results):
        success = 0
        total = 0
        for r in results:
            if isinstance(r, dict):
                for k, v in r.items():
                    total += len(v)
                    success += v.count("OK")
        logger.info(f"Run Complete. Success: {success}/{total}")

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    run_id = os.environ.get("UCV_RUN_ID") or f"ucv_async_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Simple CLI
    limit = 0
    if "--test-limit" in sys.argv:
        idx = sys.argv.index("--test-limit")
        limit = int(sys.argv[idx+1])
        
    scraper = DomainAwareScraper(run_id)
    asyncio.run(scraper.run_async(test_limit=limit))
