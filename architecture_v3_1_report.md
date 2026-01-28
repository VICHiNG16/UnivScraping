# Romanian University Scraper - Architecture Report (V3.1)

## 1. Executive Summary
This report documents the final **V3.1 Architecture**, refined after "Battle Testing" with simulated model feedback. The key innovation is a **Bronze-Silver-Gold** data lifecycle that prioritize data safety, recoverability ("Quarantine"), and historical fidelity.

### Critical Fixes Implemented (V3.1)
1.  **Composite UIDs**: `sha256(url + program_name)` to prevent collision when pages list multiple programs (fixing the "One-URL-Many-Programs" bug).
2.  **Raw Data Fidelity**: Added `spots_raw` field to the Silver Layer, capturing messy Romanian data (e.g., "30 locuri (estimat)") that would fail strict integer validation.
3.  **Config Hygiene**: Enforced automatic URL trimming to prevent "silent failures" from config whitespace.

---

## 2. The Bronze-Silver-Gold Lifecycle

| Layer | Purpose | Storage Path | Schema/Format |
| :--- | :--- | :--- | :--- |
| **Bronze** | **Immutable Source of Truth**. Raw HTML snapshots. If code breaks, we replay from here. | `data/runs/{run_id}/raw/{faculty}/snapshot.html` | HTML (Binary/Text) |
| **Silver** | **Structured Extraction**. Dirty data parsed into JSON. Validated for *structure* but not *content*. | `data/runs/{run_id}/raw/{faculty}/programs/{uid}.json` | Pydantic JSON (with `_raw` fields) |
| **Gold** | **Consumer Ready**. Cleaned, normalized, flattened data. | `data/processed/ucv_programs.csv` | CSV (UTF-8) |
| **Quarantine** | **Error Isolation**. Where bad data goes to wait for manual fix. | `data/runs/{run_id}/errors/{faculty}/...` | JSON Error Report |

---

## 3. Data Schema (Silver Layer)

The `Program` entity is the core unit of value.

```json
{
  "uid": "1a38603686c5737626a9046edfc02902cebdf55c1a0f68951b522a85a2514922", 
  "run_id": "ucv_20260128T140435",
  "scraped_at": "2026-01-28T12:04:35.426767+00:00",
  "source_url": "https://ace.ucv.ro",
  "content_hash": "a1b2c3d4...",
  "entity_type": "program",
  "name": "Ingineria Sistemelor Multimedia",
  "faculty_uid": "...",
  "level": "Licenta",
  "spots_budget": null,        
  "spots_raw": "30 locuri (buget estimated)",  // << THE FIX: Preserved dirty data
  "raw_admission_text": null
}
```

---

## 4. Operational Workflow

### Input
*   **Directive**: `directives/scrape_ucv.md` (Human Protocol)
*   **Config**: `execution/scrapers/ucv/config.yaml` (Machine Config)

### Execution (Scraper)
1.  **Initialize**: Load config, trim URLs, start `PoliteHTTPClient`.
2.  **Run Loop**: For each Faculty:
    *   **Fetch**: Get HTML.
    *   **Snapshot**: Save `snapshot.html`.
    *   **Extract**: Parse `metadata` and `programs`.
    *   **Validate**:
        *   Generate Composite UID (`url` + `name`).
        *   Save valid entities to `raw/`.
        *   Catch exceptions -> Save to `errors/`.

### Processing (Exporter)
1.  **Aggregate**: Read all JSONs from `raw/*/programs/`.
2.  **Refine**: 
    *   Normalize text (`RomanianTextNormalizer`).
    *   Select fields for CSV.
3.  **Export**: Write `data/processed/ucv_programs.csv`.

---

## 5. Verification Results
The Pilot run (`ucv_20260128T140435`) was successful.
*   **Input**: Configured `https://ace.ucv.ro`.
*   **Result**: 
    *   1 Faculty Entity extracted.
    *   1 Program Entity extracted ("Ingineria Sistemelor Multimedia").
    *   `spots_raw` correctly populated with "30 locuri (buget estimated)".
    *   CSV generated validly.

## 6. Next Steps for Optimization
1.  **PDF Parser**: Implement `pdf_parser.py` (currently a stub) to actually fill `spots_budget` from PDFs.
2.  **Dynamic Discovery**: Replace `config.yaml` hardcoded list with a crawler for `ucv.ro/faculties`.
