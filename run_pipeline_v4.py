
import logging
from datetime import datetime
import sys
import os

# Ensure execution modules are in path
sys.path.append(os.getcwd())

from execution.base.scraper_base import BaseScraper
from execution.scrapers.ucv.adapter import UCVAdapter

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    run_id = f"custom_run_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    logger = logging.getLogger("run_pipeline_v4")
    logger.info(f"Starting Full Pipeline Run: {run_id}")
    
    try:
        adapter = UCVAdapter()
        scraper = BaseScraper(run_id=run_id, adapter=adapter)
        scraper.run()
        logger.info("Pipeline Run Completed Successfully.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Pipeline Failed: {e}", exc_info=True)
        sys.exit(1)
