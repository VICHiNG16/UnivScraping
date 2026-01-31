import json
import glob
from pathlib import Path
import sys

def aggregate(run_id: str):
    base_dir = Path(f"data/runs/{run_id}/raw")
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    files = glob.glob(str(base_dir / "*" / "programs" / "*.json"))
    all_programs = []
    
    print(f"Aggregating {len(files)} program files...")
    
    for f in files:
        with open(f, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
            all_programs.append(data)
    
    out_path = output_dir / "ucv_final.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_programs, f, indent=2, ensure_ascii=False)
        
    print(f"Saved aggregated JSON to {out_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python execution/processors/aggregate_json.py <run_id>")
        sys.exit(1)
    aggregate(sys.argv[1])
