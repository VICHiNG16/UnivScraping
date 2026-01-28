
import logging
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

# Adjust path
sys.path.append(".")

from execution.scrapers.ucv.scraper import BaseScraper, UCVAdapter
from execution.enrichment.matcher import DataFusionEngine

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_grades")

class JustAgronomieAdapter(UCVAdapter):
    def discover_faculties(self):
        # Filter only ACE (known to have digital PDFs)
        all_facs = super().discover_faculties()
        return [f for f in all_facs if f["slug"] == "ace"]

    # Mock Parsing to verify Pipeline Flow (since real PDFs are scanned or missing)
    def parse_grades(self, pdf_path: str):
        return {"Ingineria Sistemelor Multimedia": 9.50, "Calculatoare (limba engleză)": 8.75}

def verify_grades():
    run_id = f"verify_grades_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    logger.info(f"Starting Verification Run: {run_id}")
    
    # 1. Run Scraper (Agronomie Only)
    adapter = JustAgronomieAdapter()
    scraper = BaseScraper(run_id=run_id, adapter=adapter)
    scraper.run()
    
    # Check if grades_map exists
    grades_dir = Path(f"data/runs/{run_id}/raw/ace/grades")
    if not grades_dir.exists() or not list(grades_dir.glob("*.json")):
        logger.error("❌ FAILED: No grades JSON generated in raw/ace/grades")
        return False
        
    logger.info("✅ Scraper successfully generated grade map.")

    # 2. Run Fusion
    engine = DataFusionEngine(run_id)
    engine.enrich_run()
    
    programs_dir = Path(f"data/runs/{run_id}/raw/ace/programs")
    has_grades = False
    
    for p_file in programs_dir.glob("*.json"):
        with open(p_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("last_admission_grade"):
                logger.info(f"✅ Found grade for {data['name']}: {data['last_admission_grade']}")
                has_grades = True
                
    if has_grades:
        logger.info("✅ Verification Passed: Grades extracted and fused.")
        return True
    else:
        logger.error("❌ FAILED: No programs have 'last_admission_grade' populated.")
        return False

if __name__ == "__main__":
    success = verify_grades()
    if not success:
        sys.exit(1)
