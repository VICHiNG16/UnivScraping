
import logging
import sys
import json
from pathlib import Path
from datetime import datetime
import shutil
import os
from execution.enrichment.matcher import DataFusionEngine, RomanianProgramMatcher

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_conflict")

def verify_conflict_modeling():
    logger.info("Starting Conflict Modeling Verification...")
    
    # 1. Setup Mock Engine
    test_run_dir = "data/runs/test_run"
    import shutil
    import os
    if os.path.exists(test_run_dir):
        shutil.rmtree(test_run_dir)
    
    slug = "test_faculty"
    (Path(test_run_dir) / "raw" / slug / "programs").mkdir(parents=True, exist_ok=True)
    
    engine = DataFusionEngine("test_run")
    
    # 2. Create Dummy Program
    slug = "test_faculty"
    prog = {
        "uid": "123",
        "name": "Informatica",
        "level": "Licenta",
        "entity_type": "program",
        "faculty_uid": "fac_123",
        "faculty_slug": slug,
        "evidence": {} # Initialize
    }
    programs = [prog]
    
    # 3. Create Conflicting Candidates
    # Candidate A: Low Score, 100 spots
    rows_A = [{"program_name": "Informatica", "spots_budget": 100, "spots_tax": 50, "level": "Licenta"}]
    url_A = "http://test.com/weak.pdf"
    score_A = 50 
    
    # Candidate B: High Score, 150 spots
    rows_B = [{"program_name": "Informatica", "spots_budget": 150, "spots_tax": 75, "level": "Licenta"}]
    url_B = "http://test.com/strong.pdf"
    score_B = 90
    
    # 4. Simulate Fusion Loop
    logger.info("Fusing Candidate A (Weak)...")
    engine._fuse_data(slug, programs, rows_A, url_A, "fac_123", likelihood_score=score_A, source_name="Weak PDF")
    
    logger.info("Fusing Candidate B (Strong)...")
    engine._fuse_data(slug, programs, rows_B, url_B, "fac_123", likelihood_score=score_B, source_name="Strong PDF")
    
    # 5. Assertions
    p = programs[0]
    
    # Evidence Check
    evidence_list = p.get("evidence", {}).get("spots", [])
    if len(evidence_list) != 2:
        logger.error(f"❌ FAILED: Expected 2 evidence entries, found {len(evidence_list)}")
        return False
        
    logger.info("✅ Evidence collection working (2/2 entries found).")
    
    # Arbitration Check
    if p["spots_budget"] != 150:
        logger.error(f"❌ FAILED: Arbitration failed. Expected 150 spots, got {p.get('spots_budget')}")
        return False
        
    if p["metadata"]["best_source_score"] < 90: # Should rely on B's score roughly
         logger.error(f"❌ FAILED: Metadata score too low: {p['metadata']['best_source_score']}")
         return False

    logger.info(f"✅ Arbitration Passed: Winner = {p['spots_budget']} spots (Source: {p['metadata']['pdf_source']})")
    
    # 6. Reverse Order Test (Ensure order independence)
    # Reset
    prog["evidence"] = {}
    prog["spots_budget"] = 0
    prog["metadata"] = {}
    
    logger.info("Testing Reverse Order (Strong then Weak)...")
    engine._fuse_data(slug, programs, rows_B, url_B, "fac_123", likelihood_score=score_B, source_name="Strong PDF")
    engine._fuse_data(slug, programs, rows_A, url_A, "fac_123", likelihood_score=score_A, source_name="Weak PDF")
    
    if p["spots_budget"] != 150:
        logger.error(f"❌ FAILED: Reverse Order Arbitration failed. Got {p.get('spots_budget')}")
        return False
        
    logger.info("✅ Reverse Order Passed.")
    return True

if __name__ == "__main__":
    if verify_conflict_modeling():
        sys.exit(0)
    else:
        sys.exit(1)
