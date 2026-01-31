# Codex Mission: Scalability & Intelligence Upgrade

**Role**: Builder
**Objective**: Implement Phase 8.1 (Truth Ranker) and Phase 11.1 (Adapter Factory).

---

## 1. Implement `PDFTruthRanker` (Phase 8.1)
**Goal**: Select the "Truth PDF" based on evidence quality, not just keywords.

### Action: Create `execution/enrichment/pdf_ranker.py`
```python
import re
from typing import Dict, List

class PDFTruthRanker:
    def __init__(self, admission_year: int = 2026):
        self.target_year = admission_year

    def rank_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """
        Scores PDFs based on metadata signals.
        Returns sorted list (best first).
        """
        scored = []
        for c in candidates:
            score = 0
            text_lower = (c.get("link_text") or "").lower() + " " + (c.get("pdf_url") or "").lower()
            
            # Signal 1: Year Match (Highest Priority)
            if str(self.target_year) in text_lower:
                score += 50
            elif str(self.target_year - 1) in text_lower:
                score += 10 # Backup year
            
            # Signal 2: Content Type Keywords
            if "cifra" in text_lower or "locuri" in text_lower:
                score += 30 # High value
            elif "ghid" in text_lower or "metodologie" in text_lower:
                score += 5  # Low value (informational)
            elif "grile" in text_lower or "tematica" in text_lower:
                score -= 20 # Negative value (exam material)
            
            # Signal 3: File Properties (if available)
            # e.g., prefer larger files (likely full tables) vs tiny ones
            
            c["stage_a_score"] = score
            scored.append(c)
            
        return sorted(scored, key=lambda x: x["stage_a_score"], reverse=True)
```

### Action: Integrate into `matcher.py`
- Import `PDFTruthRanker`.
- In `_identify_spots_pdf`, replace the current heuristic loop with:
```python
ranker = PDFTruthRanker(admission_year=datetime.now().year)
candidates = ranker.rank_candidates(pdf_queue)
# Then use the top candidate
```

---

## 2. Implement Adapter Factory (Phase 11.1)
**Goal**: Allow `BaseScraper` to load *any* university adapter dynamically.

### Action: Create `execution/scrapers/factory.py`
```python
import importlib
from execution.scrapers.adapter_interface import UniversityAdapter

class ScraperFactory:
    @staticmethod
    def get_adapter(university_slug: str) -> UniversityAdapter:
        try:
            # Dynamic import: execution.scrapers.{slug}.adapter
            module_path = f"execution.scrapers.{university_slug}.adapter"
            module = importlib.import_module(module_path)
            
            # Expecting a class named 'Adapter' or similar convention
            # For now, let's assume the module exposes a specific class or we inspect it
            if hasattr(module, "UCVAdapter"):
                return module.UCVAdapter()
            # Add general logic to find subclass of UniversityAdapter
            raise ValueError(f"No Adapter class found in {module_path}")
            
        except ImportError as e:
            raise ImportError(f"Could not load adapter for '{university_slug}': {e}")
```

### Action: Refactor `execution/base/scraper_base.py`
- Remove `from execution.scrapers.ucv.adapter import UCVAdapter`.
- Use `ScraperFactory` in `__init__` or `run()`:
```python
# Old
self.adapter = UCVAdapter()

# New
from execution.scrapers.factory import ScraperFactory
self.adapter = ScraperFactory.get_adapter(config["university_slug"])
```

---

## 3. Verify
- Run `run_pipeline_v4.py` (it should still work for UCV).
- Check logs to see `PDFTruthRanker` scoring output.
