import csv
import json
import glob
from pathlib import Path
from typing import List

class CSVExporter:
    """
    Gold Layer: Converts validated JSONs to consumer-ready CSVs.
    """
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.base_dir = Path(f"data/runs/{run_id}/raw")
        self.output_dir = Path("data/processed")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self):
        """
        Scan hierarchical JSONs and flatten to CSV.
        """
        programs_row = []
        
        # Glob patterns to find all program JSONs nested in faculties
        # Path: data/runs/{run_id}/raw/{faculty_slug}/programs/{uid}.json
        files = glob.glob(str(self.base_dir / "*" / "programs" / "*.json"))
        
        for f in files:
            with open(f, "r", encoding="utf-8") as json_file:
                data = json.load(json_file)
                # Flatten simple fields
                row = {
                    "uid": data.get("uid"),
                    "name": data.get("name"),
                    "level": data.get("level"),
                    "spots_budget": data.get("spots_budget"),
                    "spots_tax": data.get("spots_tax"),
                    "spots_raw": data.get("spots_raw"),
                    "source_type": data.get("source_type", "unknown"),
                    "accuracy_confidence": data.get("accuracy_confidence", 0.0),
                    "language": data.get("language"),
                    "url": data.get("source_url")
                }
                programs_row.append(row)
        
        if programs_row:
            keys = programs_row[0].keys()
            out_file = self.output_dir / "ucv_programs.csv"
            with open(out_file, "w", newline="", encoding="utf-8-sig") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=keys)
                writer.writeheader()
                writer.writerows(programs_row)
            print(f"Exported {len(programs_row)} programs to {out_file}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m execution.processors.export <run_id>")
        sys.exit(1)
    exporter = CSVExporter(sys.argv[1])
    exporter.export()
