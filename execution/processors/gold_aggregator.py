
import csv
import json
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime

class GoldAggregator:
    """
    Aggregates Silver Layer JSONs into Gold Layer CSVs.
    """
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.base_dir = Path(f"data/runs/{run_id}")
        self.raw_dir = self.base_dir / "raw"
        self.logger = logging.getLogger("gold_aggregator")

    def aggregate(self):
        """
        Reads all program JSONs from all faculties and creates a master CSV.
        """
        self.logger.info("Starting Gold Layer Aggregation...")

        all_programs = []

        # Iterate over all faculty directories in raw/
        if not self.raw_dir.exists():
            self.logger.warning("No raw data found.")
            return

        for faculty_dir in self.raw_dir.iterdir():
            if not faculty_dir.is_dir(): continue

            programs_dir = faculty_dir / "programs"
            if not programs_dir.exists(): continue

            for p_file in programs_dir.glob("*.json"):
                try:
                    with open(p_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        all_programs.append(data)
                except Exception as e:
                    self.logger.error(f"Failed to read {p_file}: {e}")

        if not all_programs:
            self.logger.warning("No programs found to aggregate.")
            return

        # Define CSV Columns
        columns = [
            "uid", "name", "faculty_slug", "level", "duration_years",
            "spots_budget", "spots_tax", "last_admission_grade",
            "source_url", "scraped_at"
        ]

        output_path = self.base_dir / "ucv_programs.csv"

        try:
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(all_programs)

            self.logger.info(f"Successfully exported {len(all_programs)} programs to {output_path}")
        except Exception as e:
            self.logger.error(f"Failed to write CSV: {e}")
