
import json
import logging
import asyncio
import aiohttp
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger("pdf_downloader")

class PDFDownloader:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.base_dir = Path(f"data/runs/{run_id}/raw")

    async def download_all(self):
        if not self.base_dir.exists(): return
        
        async with aiohttp.ClientSession() as session:
            for faculty_dir in self.base_dir.iterdir():
                if not faculty_dir.is_dir(): continue
                
                queue_path = faculty_dir / "pdf_queue.json"
                if not queue_path.exists(): continue
                
                with open(queue_path, "r", encoding="utf-8") as f:
                    queue = json.load(f)
                
                logger.info(f"[{faculty_dir.name}] Processing {len(queue)} PDFs...")
                updated = False
                
                for item in queue:
                     if item.get("status") != "queued": continue
                     
                     url = item["pdf_url"]
                     filename = Path(url).name
                     # Basic sanitization
                     filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in "._-"])
                     local_path = faculty_dir / "pdfs" / filename
                     local_path.parent.mkdir(exist_ok=True)
                     
                     if local_path.exists():
                         item["local_path"] = str(local_path)
                         item["status"] = "downloaded"
                         updated = True
                         continue

                     try:
                         async with session.get(url) as resp:
                             if resp.status == 200:
                                 content = await resp.read()
                                 with open(local_path, "wb") as f:
                                     f.write(content)
                                 item["local_path"] = str(local_path)
                                 item["status"] = "downloaded"
                                 updated = True
                                 logger.info(f"Downloading {filename}")
                             else:
                                 logger.warning(f"Failed {url}: {resp.status}")
                     except Exception as e:
                         logger.error(f"Error {url}: {e}")
                
                if updated:
                    with open(queue_path, "w", encoding="utf-8") as f:
                        json.dump(queue, f, indent=2)

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python download_pdfs.py <run_id>")
        sys.exit(1)
        
    downloader = PDFDownloader(sys.argv[1])
    asyncio.run(downloader.download_all())
