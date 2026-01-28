
import os
import sys
import subprocess
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pipeline")

def run_command(cmd: list):
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Command failed: {result.stderr}")
        sys.exit(1)
    logger.info("Success.")
    return result.stdout.strip()

def main():
    # 1. Start Async Scraper
    # This creates a run_id internally. We need to capture it or force it.
    # scraper_async prints logs. Let's look at how to get the ID.
    # It constructs run_id = f"ucv_async_{datetime.now()...}"
    # Let's Modify scraper_async to accept a RUN_ID arg or print it clearly.
    # For now, let's generate one here and pass it if possible, OR assume scraper_async
    # is the Entry Point.
    
    # Actually, simpler: Generate Run ID here.
    run_id = f"ucv_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Starting Campaign: {run_id}")
    
    # 1. Async Scraper (Modified to accept run_id via arg if we updated it?
    # CLI in scraper_async: scraper = DomainAwareScraper(run_id) 
    # But main block generates its own. 
    # Let's pass it via env var or modify scraper_async slightly to take arg?
    # Quick fix: Pass it as first arg if not flag?
    # Let's update scraper_async.py to accept run_id as arg.
    
    # Assuming I can't easily edit scraper_async via this script, 
    # I'll rely on scraper_async printing the ID or finding the latest dir.
    # BUT, to be robust, I will modify scraper_async CLI in the next step.
    
    # Generate Run ID
    run_id = f"ucv_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"=== Starting Pipeline Run: {run_id} ===")
    
    # 0. Pass run_id to scraper_async via a temporary config file or just hack it?
    # Better: Update scraper_async to check env var UCV_RUN_ID
    os.environ["UCV_RUN_ID"] = run_id
    
    # 1. Async Scraper (Discovery & Snapshot)
    logger.info("--- Step 1: Async Scraping (HTML Discovery) ---")
    # We use subprocess to run it, assuming it picks up the env var or generates a new one.
    # Wait, scraper_async generates its own ID in __main__. 
    # We need to tell it to use OUR run_id.
    # Let's modify scraper_async.py main block quickly before running this.
    # Or just capture the output log to find the run_id it used?
    # No, controlling it is better.
    
    # Assuming we modify scraper_async to read env var:
    run_command([sys.executable, "execution/scrapers/ucv/scraper_async.py"])
    
    # 2. Parse Snapshots (Silver Layer)
    logger.info("--- Step 2: Parsing Snapshots ---")
    run_command([sys.executable, "execution/processors/parse_snapshots.py", run_id])
    
    # 3. Download PDFs
    logger.info("--- Step 3: Downloading PDFs ---")
    run_command([sys.executable, "execution/processors/download_pdfs.py", run_id])
    
    # 4. Matcher (Enrichment)
    logger.info("--- Step 4: Multi-Signal Matching ---")
    run_command([sys.executable, "execution/enrichment/matcher.py", run_id])
    
    # 5. RAG Conversion (Gold Layer)
    logger.info("--- Step 5: RAG Conversion ---")
    run_command([sys.executable, "execution/processors/rag_converter.py", run_id])
    
    logger.info(f"=== Pipeline Complete. Data in data/runs/{run_id} ===")
