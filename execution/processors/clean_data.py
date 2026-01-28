import csv
import json
import re
from pathlib import Path
from typing import List, Dict, Any

class DataCleaner:
    def __init__(self, input_csv: str, output_json: str):
        self.input_csv = Path(input_csv)
        self.output_json = Path(output_json)
    
    def run(self):
        if not self.input_csv.exists():
            print(f"Error: {self.input_csv} not found.")
            return

        print(f"Loading {self.input_csv}...")
        raw_data = []
        with open(self.input_csv, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_data.append(row)
        
        cleaned_data = self._process_rows(raw_data)
        
        print(f"Saving {len(cleaned_data)} records to {self.output_json}...")
        with open(self.output_json, "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
            
    def _process_rows(self, rows: List[Dict]) -> List[Dict]:
        results = []
        
        for row in rows:
            # 1. Filter Low Quality
            confidence = float(row.get("accuracy_confidence", 0))
            spots_budget = self._parse_int(row.get("spots_budget"))
            spots_tax = self._parse_int(row.get("spots_tax"))
            
            # Keep if high confidence OR has valid spots data
            if confidence < 0.4 and (spots_budget is None or spots_budget == 0):
                continue
            
            # 2. Clean Name
            raw_name = row.get("name", "")
            clean_name = self._clean_name(raw_name)
            
            # 3. Detect Faculty (from URL or uid? uid is unique per program)
            # URL: https://ace.ucv.ro/... -> ace
            url = row.get("url", "")
            faculty_code = "unknown"
            if url:
                # regex for subdomain
                m = re.search(r'https?://([^.]+)\.ucv\.ro', url)
                if m:
                    faculty_code = m.group(1)
            
            # 4. Construct Final Object
            obj = {
                "faculty_code": faculty_code,
                "program_name": clean_name,
                "degree_level": row.get("level", "Licenta"),
                "spots": {
                    "budget": spots_budget if spots_budget is not None else 0,
                    "tax": spots_tax if spots_tax is not None else 0
                },
                "metadata": {
                    "source_url": url,
                    "source_confidence": "high" if confidence > 0.8 else "medium",
                    "original_uid": row.get("uid")
                }
            }
            results.append(obj)
            
        return results

    def _clean_name(self, name: str) -> str:
        if not name: return "Unknown"
        
        # Remove (aici), (detalii), etc
        name = re.sub(r'\(\s*(aici|detalii|vezi|link)\s*\)', '', name, flags=re.IGNORECASE)
        
        # Remove [Metadata]
        name = re.sub(r'\[.*?\]', '', name)
        
        # Remove extra spaces
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Title Case (Simple)
        # Handle specialized casing? For now, .title() is decent but might break acronyms
        # Better: Capitalize first letter, keep rest? Or robust Title Case?
        # Let's use robust logic or just standard title()
        # "Ingineria Sistemelor Multimedia" is good.
        # "CALCULATOARE" -> "Calculatoare"
        if name.isupper():
            name = name.title()
        
        # Fix specific punctuation
        name = name.replace(" ,", ",")
        
        return name

    def _parse_int(self, val) -> int:
        if not val: return 0
        try:
            return int(float(val)) # Handle "10.0" strings
        except:
            return 0

if __name__ == "__main__":
    cleaner = DataCleaner("data/processed/ucv_programs.csv", "data/processed/ucv_final.json")
    cleaner.run()
