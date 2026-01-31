
import json
from pathlib import Path

def aggregate_run(run_id: str):
    base_dir = Path(f"data/runs/{run_id}/raw")
    all_programs = []
    
    print(f"Aggregating run: {run_id}")
    
    for faculty_dir in base_dir.iterdir():
        if not faculty_dir.is_dir(): continue
        
        programs_dir = faculty_dir / "programs"
        if not programs_dir.exists(): continue
        
        for p_file in programs_dir.glob("*.json"):
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    all_programs.append(data)
            except Exception as e:
                print(f"Error reading {p_file}: {e}")
                
    output_path = Path("data/processed/ucv_final.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_programs, f, indent=2, ensure_ascii=False)
        
    print(f"✅ Aggregated {len(all_programs)} programs into {output_path}")

if __name__ == "__main__":
    # Aggregating the latest run (Run 5 - TableParser)
    aggregate_run("custom_run_20260129T172304")
