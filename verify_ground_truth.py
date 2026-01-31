
import json
from pathlib import Path

def normalize_name(name):
    """Normalize program names for loose matching."""
    return name.lower().replace("ă", "a").replace("â", "a").replace("ș", "s").replace("ț", "t").replace("î", "i").replace("-", " ").strip()

def verify_ground_truth():
    # Load Ground Truth
    gt_path = Path("models/research/firecrawl.json")
    if not gt_path.exists():
        print("❌ Ground Truth file not found!")
        return

    with open(gt_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)
        # Convert dict of dicts to list if needed, or handle direct list
        if isinstance(gt_data, dict):
            gt_items = list(gt_data.values())
        else:
            gt_items = gt_data

    # Load Pipeline Output
    pipeline_path = Path("data/processed/ucv_final.json")
    if not pipeline_path.exists():
        print("❌ Pipeline output not found!")
        return
        
    with open(pipeline_path, "r", encoding="utf-8") as f:
        pipeline_items = json.load(f)

    print(f"Loaded {len(gt_items)} Ground Truth items.")
    print(f"Loaded {len(pipeline_items)} Pipeline items.")

    # Index Pipeline items by normalized name
    pipeline_map = {normalize_name(p['name']): p for p in pipeline_items}
    
    matches_exact = 0
    matches_fuzzy = 0
    missing = []
    
    faculty_stats = {}

    for gt in gt_items:
        fac = gt.get('faculty', 'Unknown')
        if fac not in faculty_stats: faculty_stats[fac] = {'total': 0, 'found': 0}
        faculty_stats[fac]['total'] += 1
        
        gt_name = normalize_name(gt['name'])
        
        # Try finding match
        match = None
        
        # 1. Exact Normalized Match
        if gt_name in pipeline_map:
            match = pipeline_map[gt_name]
            matches_exact += 1
        else:
            # 2. Substring Match (simplified)
            for p_name, p_data in pipeline_map.items():
                if gt_name in p_name or p_name in gt_name:
                    match = p_data
                    matches_fuzzy += 1
                    break
        
        if match:
            faculty_stats[fac]['found'] += 1
        else:
            missing.append(gt)

    print("\n=== Verification Results ===")
    print(f"✅ Exact Matches: {matches_exact}")
    print(f"⚠️ Partial Matches: {matches_fuzzy}")
    print(f"❌ Missing: {len(missing)}")
    print(f"Recall: {((matches_exact + matches_fuzzy) / len(gt_items) * 100):.1f}%")

    print("\n=== Missing by Faculty ===")
    for fac, stats in faculty_stats.items():
        if stats['found'] < stats['total']:
            print(f"- {fac}: Found {stats['found']}/{stats['total']} ({stats['found']/stats['total']*100:.0f}%)")

if __name__ == "__main__":
    verify_ground_truth()
