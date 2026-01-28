# Romanian University Scraper - V3 Architecture & Workflow

## 1. Overview
This project implements a robust **Data Pipeline** for scraping Romanian university data (starting with UCV). Unlike simple scripts, it uses a **Bronze-Silver-Gold** data lifecycle to ensure durability, auditability, and error resilience.

**Core Philosophy:** "Never crash on bad data; Quarantine it. Never lose history; Snapshot it."

---

## 2. Directory Structure

| Directory | Purpose | Key Files |
| :--- | :--- | :--- |
| **`directives/`** | **INPUT**: Human-readable protocols. | `scrape_ucv.md` |
| **`execution/`** | **CODE**: Logic for scraping & processing. | `models/`, `scrapers/`, `processors/` |
| **`data/`** | **OUTPUT**: Storage for all artifacts. | `runs/{run_id}/`, `processed/` |

---

## 3. The Pipeline: Start to Finish

### Step 1: Definition (Input)
*   **Directive**: A human defines the goal in `directives/scrape_ucv.md` (e.g., "Find Admission spots in PDF X").
*   **Configuration**: Target URLs and CSS selectors are defined in `execution/scrapers/ucv/config.yaml`.
    *   *Input*: `url: "https://ace.ucv.ro"`, `slug: "ace"`

### Step 2: Execution - Bronze Layer (Snapshot)
The `UCVScraper` starts a new session (Run ID: `ucv_20260128...`).
1.  **Fetch**: `PoliteHTTPClient` requests the URL (with user-agent rotation).
2.  **Hash**: Calculates `SHA256(canonical_url)` for a stable UID and `SHA256(html_content)` for change detection.
3.  **Snapshot**: Saves the raw HTML **before** any parsing.
    *   *Output*: `data/runs/{run_id}/raw/ace/snapshot.html`

### Step 3: Execution - Silver Layer (Extraction)
1.  **Parse**: `BeautifulSoup` extracts raw text using selectors from `config.yaml`.
2.  **Provenance**: Attaches metadata (Run ID, Timestamp, Source URL).
3.  **Validation**: Data is passed to **Pydantic Models** (`Faculty`, `Program`).
    *   **If Valid**: Saved as structured JSON.
        *   *Output*: `data/runs/{run_id}/raw/ace/programs/{uid}.json`
    *   **If Invalid**: Caught by `BaseScraper`, logged to `errors/`, and the script continues (does not crash).
        *   *Output*: `data/runs/{run_id}/errors/ace/error_timestamp.json`

### Step 4: Processing - Gold Layer (Refinement)
1.  **Export**: `CSVExporter` reads the Silver Layer JSONs.
2.  **Normalize**: `RomanianTextNormalizer` cleans the text (fixing diacritics like `ş` -> `ș`).
3.  **Flatten**: Hierarchical data is converted to flat CSV rows.
    *   *Output*: `data/processed/ucv_programs.csv`
    *   *Output*: `data/processed/ucv_faculties.csv`

---

## 4. Input & Output Schemas

### Input: `config.yaml`
```yaml
faculties:
  - name: "Facultatea de Automatică"
    slug: "ace"
    url: "https://ace.ucv.ro"
```

### Output: Silver JSON (`program.json`)
```json
{
  "uid": "0e82e7c6...",          // SHA256(canonical_url)
  "run_id": "ucv_2026...",
  "entity_type": "program",
  "name": "Ingineria Sistemelor Multimedia",
  "spots_budget": 30,            // Integer
  "source_url": "https://ace.ucv.ro",
  "content_hash": "a1b2c3d4..."  // For detecting changes next run
}
```

### Output: Gold CSV (`ucv_programs.csv`)
```csv
uid,name,level,spots_budget,language,url
0e82e7...,Ingineria Sistemelor Multimedia,Licenta,30,Romanian,https://ace.ucv.ro
```

---

## 5. How to Validate & Change
This architecture is modular. You can change specific parts without breaking the whole:

*   **Want to change selectors?** Edit `config.yaml`.
*   **Want to add a new field?** Update `execution/models/program.py`.
*   **Want to fix text cleaning?** Update `execution/processors/normalize.py`.
*   **Want to try a new University?** Create `execution/scrapers/upb/` and inherit `BaseScraper`.
