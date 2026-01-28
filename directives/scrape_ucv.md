# Directives: Scrape University of Craiova (UCV)

## Objective
Extract structural data (Faculties, Programs) and Admission Statistics (Spots, Last Admission Grades) for the University of Craiova.

## Critical Information Sources
| Data Point | Source Type | URL Pattern | Notes |
| :--- | :--- | :--- | :--- |
| **Faculty List** | HTML | `https://www.ucv.ro/structura_academica/facultati/` | Main discovery hub |
| **Programs (Bachelor)** | HTML | `https://www.ucv.ro/invatamant/programe_academice/licenta/` | Centralized list (often outdated, cross-check with faculty sites) |
| **Admission Spots (2025/2026)** | **PDF** | `https://www.ucv.ro/admitere/` -> "Cifra de școlarizare" | **CRITICAL**: Spots often ONLY exist in PDFs. |
| **Faculty Sites** | Mixed | `https://*.ucv.ro` | Heterogeneous (WordPress, Custom PHP, Static). |

## Provenance Rules
1.  **UID Generation**: Use `sha256(canonical_url)` for all entities.
2.  **Snapshots**: SAVE HTML BEFORE PARSING. Path: `data/runs/{run_id}/raw/{faculty_slug}/snapshot.html`.
3.  **PDFs**: If a PDF is found, download it to `data/runs/{run_id}/raw/{faculty_slug}/pdfs/`.

## Known Faculty Quirks (Heterogeneity)
*   **Engineering (Automatică)**: Tables nested deep in divs. Use strict selectors.
*   **Economics (FEAA)**: WordPress-based. Good structured data but heavy reliance on classes.
*   **Theology**: Non-standard URL structure.
*   **Letters**: mostly static HTML, sometimes malformed.

## Validation Strategy
1.  **Extract All**: Do not crash on missing fields. Capture raw text.
2.  **Quarantine**: If critical fields (Name, URL) are missing, save to `data/runs/{run_id}/errors/`.
3.  **Manual Review**: Check `errors/` folder after every run.

## Output Format (Gold Layer)
*   `ucv_faculties.csv`: `uid, name, slug, url, programs_count, last_updated`
*   `ucv_programs.csv`: `uid, faculty_uid, name, level, spots_budget, spots_tax, last_admission_grade, url`
