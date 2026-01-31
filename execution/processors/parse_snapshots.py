
import json
import logging
import yaml
from pathlib import Path


logger = logging.getLogger("snapshot_parser")

class SnapshotParser:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.base_dir = Path(f"data/runs/{run_id}/raw")
        # Instantiate scraper to access extraction logic
        from execution.scrapers.ucv.scraper import UCVScraper
        self.scraper = UCVScraper(run_id)
        
        # Load Config
        self.config = {}
        try:
            with open("execution/scrapers/ucv/config.yaml", "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Could not load ucv/config.yaml: {e}") 

    def parse_all(self):
        if not self.base_dir.exists():
            logger.error(f"Run directory {self.base_dir} does not exist.")
            return

        logger.info(f"Parsing snapshots for Run ID: {self.run_id}")
        
        # Iterate over faculty directories
        for faculty_dir in self.base_dir.iterdir():
            if not faculty_dir.is_dir(): continue
            
            slug = faculty_dir.name
            snapshot_path = faculty_dir / "snapshot.html"
            
            if not snapshot_path.exists():
                logger.warning(f"[{slug}] No snapshot found.")
                continue
                
            logger.info(f"[{slug}] Parsing snapshot...")
            
            # Read Snapshot
            with open(snapshot_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Extract Source URL (embedded in comment or from config? 
            # Scraper_async writes <!-- Source: url --> at line 1)
            source_url = "unknown"
            first_line = content.splitlines()[0]
            if "Source: " in first_line:
                source_url = first_line.split("Source: ")[1].strip().split(" ")[0] # handle comment end -->
            
            # Prepare Queues
            pdf_queue = []
            
            # Determine Faculty Name
            faculty_name = slug.upper() # Fallback
            if self.config and "faculties" in self.config:
                for f in self.config["faculties"]:
                    if f.get("slug") == slug:
                        faculty_name = f.get("name")
                        break
            
            # Setup Directories (Important!)
            self.scraper.setup_directories(slug)
            
            # Call Extraction Logic
            try:
                self.scraper._extract_from_snapshot(content, source_url, slug, faculty_name, pdf_queue)
                
                # Save Queue
                if pdf_queue:
                    queue_path = faculty_dir / "pdf_queue.json"
                    with open(queue_path, "w", encoding="utf-8") as f:
                        json.dump(pdf_queue, f, indent=2, ensure_ascii=False)
                    logger.info(f"[{slug}] Queued {len(pdf_queue)} PDFs.")
            except Exception as e:
                logger.error(f"[{slug}] Parsing failed: {e}")

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python parse_snapshots.py <run_id>")
        sys.exit(1)
        
    parser = SnapshotParser(sys.argv[1])
    parser.parse_all()
