
import logging
from datetime import datetime
from execution.base.scraper_base import BaseScraper
from execution.scrapers.ucv.adapter import UCVAdapter

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    run_id = f"ucv_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    adapter = UCVAdapter()
    
    # Instantiate Generic Scraper with Specific Adapter
    scraper = BaseScraper(run_id=run_id, adapter=adapter)
    
    # Run
    scraper.run()
