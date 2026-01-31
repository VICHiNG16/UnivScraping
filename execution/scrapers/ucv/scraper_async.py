import asyncio
import aiohttp
import logging
import time
import socket
import os
import random
from typing import Dict, List, Optional
from pathlib import Path
from asyncio import Semaphore
import yaml
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# local imports
from execution.scrapers.ucv.adapter import UCVAdapter
from execution.base.browser_manager import BrowserManager
from execution.models.provenance import ProvenanceMixin

logger = logging.getLogger("async_scraper")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def _random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7"
    }

class CircuitBreaker:
    def __init__(self, failure_threshold=3, reset_timeout=300):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = 0

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()

    def record_success(self):
        self.failures = 0

    def is_open(self):
        if self.failures >= self.failure_threshold:
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.record_success()  # Reset implies half-open success for simplicity here
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

        # Adapter & browser
        self.adapter = UCVAdapter()
        self.browser = BrowserManager()
        self.executor = ThreadPoolExecutor(max_workers=2)

        # aiohttp defaults
        self.global_timeout = settings.get("global_timeout", 45)
        self.request_retries = settings.get("request_retries", 3)

    def _get_domain_group(self, url: str) -> str:
        for group_name, cfg in self.groups_config.items():
            for domain in cfg.get("domains", []):
                if domain in url:
                    return group_name
        return "ucv_subdomains" if ".ucv.ro" in url else "ucv_main"

    async def _async_get_with_retries(self, session: aiohttp.ClientSession, url: str, max_retries: int = 3):
        """
        Robust GET with exponential backoff and custom headers.
        """
        backoff = 1.0
        for attempt in range(1, max_retries + 1):
            headers = _random_headers()
            try:
                timeout = aiohttp.ClientTimeout(total=self.global_timeout, connect=10)
                async with session.get(url, timeout=timeout, headers=headers, allow_redirects=True) as resp:
                    text = await resp.text(errors='replace')
                    return resp.status, text
            except Exception as e:
                logger.warning(f"GET error for {url} attempt {attempt}/{max_retries}: {e}")
                if attempt == max_retries:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2

    async def run_async(self, test_limit: int = 0):
        faculties = self.config.get("faculties", [])
        if test_limit > 0:
            faculties = faculties[:test_limit]
            
        # Force IPv4 to avoid getaddrinfo errors on some envs
        connector = aiohttp.TCPConnector(family=socket.AF_INET, limit_per_host=5)
        
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
        pdf_queue = []
        programs_found_total = 0

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
                try:
                    logger.info(f"[{slug}] Fetching {url} ...")
                    status, html = await self._async_get_with_retries(session, url, max_retries=self.request_retries)
                    if status != 200:
                        logger.warning(f"[{slug}] HTTP {status} for {url}")
                        if 500 <= status < 600:
                            breaker.record_failure()
                        results.append(f"HTTP_{status}")
                        continue

                    # Save Snapshot (include Source comment)
                    self._save_snapshot(slug, html, url)

                    # Adapter extraction (reuse same logic as BaseScraper)
                    pdf_candidates = self.adapter.extract_pdf_candidates(html, url)
                    grade_candidates = self.adapter.extract_grade_candidates(html, url)
                    programs = self.adapter.extract_programs_from_html(html, url, slug)

                    # Save programs if found
                    for p in programs:
                        p.run_id = self.run_id
                        # replicate BaseScraper save_entity contract
                        (self.base_dir / slug / "programs").mkdir(parents=True, exist_ok=True)
                        fname = f"{p.uid}.json"
                        with open(self.base_dir / slug / "programs" / fname, "w", encoding="utf-8") as f:
                            f.write(p.model_dump_json(indent=2))

                    programs_found_total += len(programs)

                    # Add pdf candidates to queue
                    existing_urls = {p["pdf_url"] for p in pdf_queue}
                    for pdf in pdf_candidates:
                        if pdf["pdf_url"] not in existing_urls:
                            pdf["faculty_slug"] = slug
                            pdf["status"] = "queued"
                            pdf_queue.append(pdf)
                            existing_urls.add(pdf["pdf_url"])

                    # If nothing was found (no programs, no pdfs), try dynamic render with Playwright
                    if not programs and not pdf_candidates:
                        logger.info(f"[{slug}] No content found via HTTP. Trying Playwright fallback for {url} ...")
                        # run BrowserManager.get_html() in thread executor because it is sync
                        html_rendered = await asyncio.get_event_loop().run_in_executor(self.executor, self.browser.get_html, url)
                        if html_rendered and len(html_rendered) > 200:
                            logger.info(f"[{slug}] Playwright returned {len(html_rendered)} bytes.")
                            self._save_snapshot(slug, html_rendered, url + " #playwright")
                            # Re-run adapter extraction
                            pdf_candidates = self.adapter.extract_pdf_candidates(html_rendered, url)
                            grade_candidates = self.adapter.extract_grade_candidates(html_rendered, url)
                            programs = self.adapter.extract_programs_from_html(html_rendered, url, slug)

                            # Save programs and queue pdfs as above
                            for p in programs:
                                p.run_id = self.run_id
                                (self.base_dir / slug / "programs").mkdir(parents=True, exist_ok=True)
                                fname = f"{p.uid}.json"
                                with open(self.base_dir / slug / "programs" / fname, "w", encoding="utf-8") as f:
                                    f.write(p.model_dump_json(indent=2))

                            existing_urls = {p["pdf_url"] for p in pdf_queue}
                            for pdf in pdf_candidates:
                                if pdf["pdf_url"] not in existing_urls:
                                    pdf["faculty_slug"] = slug
                                    pdf["status"] = "queued"
                                    pdf_queue.append(pdf)
                                    existing_urls.add(pdf["pdf_url"])

                    # Save pdf_queue.json for the faculty
                    if pdf_queue:
                        queue_path = self.base_dir / slug / "pdf_queue.json"
                        with open(queue_path, "w", encoding="utf-8") as f:
                            import json
                            json.dump(pdf_queue, f, indent=2, ensure_ascii=False)

                    breaker.record_success()
                    success = True
                    results.append("OK")

                except Exception as e:
                    logger.warning(f"[{slug}] Error {url}: {e}")
                    breaker.record_failure()
                    results.append("ERROR")

        # summary per faculty
        logger.info(f"[{slug}] Finished. Programs found: {programs_found_total}, PDFs queued: {len(pdf_queue)}")
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
