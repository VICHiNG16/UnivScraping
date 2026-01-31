import asyncio
import aiohttp
import aiofiles
import logging
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from datetime import datetime

logger = logging.getLogger("pdf_worker")

class AsyncPDFDownloader:
    """
    Resilient PDF downloader with per-domain rate limiting and circuit breakers.
    Designed for fragile academic infrastructure (UCV).
    """
    
    def __init__(self, run_id: str, max_concurrent: int = 2):
        self.run_id = run_id
        self.max_concurrent = max_concurrent  # Critical: UCV infrastructure collapses >3 concurrent
        self.base_dir = Path("data/runs") / run_id
        self.session = None
        self.circuit_breakers: Dict[str, int] = {} # Domain -> Failure Count
        self.circuit_limit = 3 # Stop after 3 consecutive failures
    
    async def __aenter__(self):
        # Conservative connector: max 2 connections PER DOMAIN (UCV subdomains share infra)
        connector = aiohttp.TCPConnector(
            limit_per_host=2,
            ssl=False,
            ttl_dns_cache=300
        )
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=60, connect=20),  # PDFs need longer timeout
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/pdf"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_domain(self, url: str) -> str:
        from urllib.parse import urlparse
        return urlparse(url).netloc

    async def download_with_backoff(self, url: str, faculty_slug: str, retry: int = 0) -> Dict[str, Any]:
        """Exponential backoff with per-domain isolation"""
        max_retries = 4
        domain = self._get_domain(url)
        
        # Check Circuit Breaker
        if self.circuit_breakers.get(domain, 0) >= self.circuit_limit:
            return {"status": "circuit_open", "error": f"Domain {domain} blocked after failures"}

        if retry >= max_retries:
            self.circuit_breakers[domain] = self.circuit_breakers.get(domain, 0) + 1
            return {"status": "failed", "error": "max_retries_exceeded"}
        
        try:
            logger.info(f"[{faculty_slug}] Downloading PDF (attempt {retry+1}): {url}...")
            
            async with self.session.get(url) as resp:
                if resp.status == 429:  # Too Many Requests
                    await asyncio.sleep(2 ** retry)
                    return await self.download_with_backoff(url, faculty_slug, retry + 1)
                
                if resp.status != 200:
                    raise Exception(f"HTTP {resp.status}")
                
                # Verify Content-Type (Basic guard)
                ctype = resp.headers.get("Content-Type", "").lower()
                if "text/html" in ctype:
                    # Broken link returning 404 page as 200 OK
                    raise Exception(f"Invalid Content-Type: {ctype} (likely HTML error page)")

                # Stream to avoid memory explosion on 50MB PDFs
                pdf_bytes = await resp.read()
                pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()[:16]
                
                # Save to faculty-specific PDF vault
                pdf_dir = self.base_dir / "raw" / faculty_slug / "pdf_vault"
                pdf_dir.mkdir(parents=True, exist_ok=True)
                pdf_path = pdf_dir / f"{pdf_hash}.pdf"
                
                async with aiofiles.open(pdf_path, "wb") as f:
                    await f.write(pdf_bytes)
                
                # Success - Reset Circuit Breaker for this domain
                self.circuit_breakers[domain] = 0
                
                return {
                    "status": "downloaded",
                    "pdf_hash": pdf_hash,
                    "local_path": str(pdf_path), # Absolute path for internal use
                    "size_mb": len(pdf_bytes) / (1024 * 1024),
                    "downloaded_at": datetime.now().isoformat()
                }
                
        except asyncio.TimeoutError:
            logger.warning(f"[{faculty_slug}] Timeout on {url} (retry {retry+1})")
            await asyncio.sleep(3 ** retry)  # Aggressive backoff for timeouts
            return await self.download_with_backoff(url, faculty_slug, retry + 1)
        
        except Exception as e:
            logger.error(f"[{faculty_slug}] Download failed: {str(e)[:100]}")
            await asyncio.sleep(2 ** retry)
            return await self.download_with_backoff(url, faculty_slug, retry + 1)
    
    async def process_faculty_queue(self, faculty_slug: str):
        """Process ALL PDFs for a faculty with concurrency control"""
        queue_path = self.base_dir / "raw" / faculty_slug / "pdf_queue.json"
        
        if not queue_path.exists():
            logger.warning(f"[{faculty_slug}] No pdf_queue.json found.")
            return
        
        # Load queue with resilience metadata
        try:
            with open(queue_path, "r", encoding="utf-8") as f:
                queue = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"[{faculty_slug}] Corruped pdf_queue.json")
            return
        
        # Filter only queued items
        pending_indices = [i for i, entry in enumerate(queue) if entry.get("status") == "queued"]
        
        if not pending_indices:
            logger.info(f"[{faculty_slug}] No pending PDFs.")
            return
        
        logger.info(f"[{faculty_slug}] Processing {len(pending_indices)} PDFs...")
        
        # Semaphore-controlled concurrency
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def bounded_download(index):
            entry = queue[index]
            async with semaphore:
                result = await self.download_with_backoff(
                    entry["pdf_url"], 
                    faculty_slug
                )
                entry.update(result)
                return index, entry
        
        # Process with concurrency control
        tasks = [bounded_download(i) for i in pending_indices]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Update queue in memory (results contains (index, entry) tuples)
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Critical Task Error: {res}")
                continue
            idx, updated_entry = res
            queue[idx] = updated_entry
        
        # Persist updated queue
        with open(queue_path, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[{faculty_slug}] PDF download phase complete")

if __name__ == "__main__":
    # Test Driver
    import sys
    # Expect run_id as arg
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python pdf_worker.py <run_id>")
        sys.exit(1)
        
    run_id = sys.argv[1]
    
    async def main():
        async with AsyncPDFDownloader(run_id) as downloader:
            # Auto-discover faculties
            run_dir = Path("data/runs") / run_id / "raw"
            if not run_dir.exists():
                print(f"Run dir {run_dir} not found")
                return
            
            for faculty_dir in run_dir.iterdir():
                if faculty_dir.is_dir():
                    await downloader.process_faculty_queue(faculty_dir.name)

    asyncio.run(main())
