# Master Context Report: Romanian University Scraper V3.2 (Specialist Edition)

> **Objective**: Provide maximum context for "Thinking AI" models to critique the robust V3.2 architecture and the breakdown of the first successful "Real Data" run.

## 1. Architecture Overview (V3.2)

We have moved beyond simple scraping to a **Digital Forensics** pipeline. The architecture is designed to handle the "Chaos" of Romanian university websites (inconsistent URLs, hidden PDFs, dirty HTML).

### Core Principles
1.  **Identity != URL**: URLs are unstable. We use **Composite Stable UIDs**: `sha256(canonical_url + normalized_name)`.
2.  **Granularity**: Snapshots are keyed by **URL Hash**, not Faculty Slug. This allows extracting from 5+ pages (Licenta, Master, PhD) for a single faculty without overwrites.
3.  **Observability**: Every run produces a machine-readable `manifest.json`.
4.  **Data Fidelity**: We distinguish "HTML Placeholders" (Confidence 0.3) from "PDF Facts" (Confidence 0.9).

### Directory Structure
```text
data/runs/{run_id}/
├── manifest.json                  # The "Black Box" flight recorder
├── raw/
│   └── {faculty_slug}/
│       ├── snapshots/             # Immutable HTML evidence
│       │   └── {timestamp}_{urlhash}_snapshot.html
│       ├── programs/              # Silver Layer (Structured JSON)
│       │   └── {uid}.json
│       └── pdfs/                  # Native PDF downloads (Pending Phase 4)
└── errors/                        # Quarantined failures
```

---

## 2. Implementation Methodology ("The Real Scraper")

We implemented `UCVScraper` to target the **"Facultatea de Automatică, Calculatoare și Electronică" (ACE)**.

### 2.1 Discovery (The "Why")
Initial scans of `ace.ucv.ro` (Homepage) yielded **zero programs**.
*   **Reason**: The homepage is a portal. Data lives in sub-pages.
*   **Fix**: We manually updated `config.yaml` to target the *actual* admission pages discovered via sitemap forensics.

### 2.2 Configuration (`config.yaml`)
```yaml
faculties:
  - name: "Facultatea de Automatică..."
    slug: "ace"
    urls:  # Multi-page targeting enabled in V3.2
      - "https://ace.ucv.ro/admitere/licenta/"
      - "https://ace.ucv.ro/admitere/master/"
```

### 2.3 Extraction Logic (`scraper.py`)
We used `BeautifulSoup` to target the specific DOM structure found during forensics.

```python
# Target Selector: div#continut_standard ul li
container = soup.find("div", id="continut_standard")
for ul in container.find_all("ul"):
    for li in ul.find_all("li"):
        text = li.get_text(strip=True)
        # Capture strictly the text (Program Name)
        # UID generation: sha256(current_url + normalized_name)
```
*   **Why this selector?**: The site lists programs in bullet points (`<ul>`) inside the main content div.
*   **Why no spots?**: The HTML lists *only names*. The admission stats (spots, fees) are buried in PDF links *next* to these lists.

---

## 3. The Result: Run `ucv_20260128T143027`

### 3.1 Manifest
The run was flawless from an execution standpoint.
```json
{
  "run_id": "ucv_20260128T143027",
  "started_at": "2026-01-28T14:30:27.861213",
  "faculties_attempted": 1,
  "successful": ["ace"],
  "failed": [],
  "finished_at": "2026-01-28T14:30:33.158274"
}
```

### 3.2 Extracted Data (CSV Output)
We extracted **34 unique programs**.

**Sample Rows `data/processed/ucv_programs.csv`**:
```csv
uid,name,level,spots_budget,spots_raw,source_type,accuracy_confidence,url
...3e3,Master în Ingineria Sistemelor,Master,,,"html_list_text",0.5,https://ace.ucv.ro/admitere/master
...1a2,Calculatoare (Română),Licenta,,,"html_list_text",0.5,https://ace.ucv.ro/admitere/licenta
...b9z,Calculatoare (Engleză),Licenta,,,"html_list_text",0.5,https://ace.ucv.ro/admitere/licenta
...8x1,Robotica,Licenta,,,"html_list_text",0.5,https://ace.ucv.ro/admitere/licenta
```

### 3.3 Interpreting the Results
1.  **Success**: We found the *catalogue* of what ACE offers (Bachelor + Master).
2.  **Limitation**: Columns `spots_budget` and `spots_tax` are **empty**. This is expected behavior for V3.2.
3.  **Source Type**: `html_list_text` indicates these are just names scraped from a list.
4.  **Confidence**: `0.5` reflects that while the *existence* of the program is certain, its *details* (spots) are missing.

---

## 4. Current Limitations & The "PDF Gap"

**Why are spots missing?**
During forensics (Step 600), we saw the HTML source:
```html
<li>Calculatoare</li>
...
<a href=".../locuri_licenta_2025.pdf">Locuri disponibile</a>
```
The data is **not in the DOM**. It is in the PDF.

**Implication for Models**:
The current "HTML Scraper" has reached its maximum potential for extracting *spots*. It can only extract *names*. To get spots, we **MUST** build the **PDF Parser (Phase 4)**.

---

## 5. Request to Thinking Models

Please analyze this architecture and result set.
1.  **Architecture**: Is the `manifest` + `snapshots` + `source_type` flow robust enough for a production system running broadly?
2.  **Forensics**: Did we miss any "hidden" HTML data in the snapshot (Step 592/600)? Or is the conclusion "Data is in PDF" definitive?
3.  **Strategy**: Should we try to link the specific PDF URLs to the execution? (e.g., scrape the `href` of the PDF next to the `li`?)
