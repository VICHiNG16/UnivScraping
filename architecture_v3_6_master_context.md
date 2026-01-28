# Master Context Report: Romanian University Scraper V3.6 (Scaled & "Forensic-Ready")

> **Use Case**: Feeding Thinking AI Models (DeepSeek, Qwen, Kimi) for Phase 4 Strategy.
> **Status**: V3.6 Implemented (Partial Scaled Run specific to infrastructure tests).
> **Date**: 2026-01-28

---

## 1. The "Specialist" Upgrade (V3.6)

Following the guidance of the models, I upgraded the architecture from a single-faculty Pilot to a **Universal Forensic Scraper**.

### 1.1 Key Architectural Changes
1.  **PDF Queue System (Kimi's Request)**:
    *   Instead of ignoring PDFs or downloading them chaotically, we now build a `pdf_queue.json` artifact per faculty in the Bronze Layer.
    *   *Implementation*: A passed-by-reference `pdf_queue` list in `_extract_from_snapshot`.

2.  **Robust Encoding Guard (DeepSeek/Kimi)**:
    *   We no longer trust `requests.encoding`.
    *   *Logic*:
        ```python
        # Force UTF-8 if server says Latin-1 (common Romanian misconfiguration)
        if resp.encoding == 'ISO-8859-1' and 'text/html' in resp.headers.get('Content-Type', ''):
             resp.encoding = 'utf-8'
        # Fallback: Check for Mojibake "Ä" vs "ă"
        if "Ä" in resp.text and "ă" not in resp.text:
             resp.encoding = 'utf-8'
        ```

3.  **Program Code Discovery (Qwen's Insight)**:
    *   Heuristic extraction of codes to enable future PDF matching.
    *   *Logic*: `text.lower().contains("englez") -> Code: ENG`.

4.  **Domain & Context Awareness**:
    *   We now detect headers like `Domeniul Calculatoare` and append `[Domain: Calculatoare]` to the child programs' metadata to preserve hierarchy.

---

## 2. Infrastructure Stress Test (Run `ucv_20260128T151617`)

I executed a scaled run against **12 Faculties**. This "Chaos Test" revealed the true state of UCV's infrastructure.

### 2.1 Results
| Faculty | Slug | Status | Finding |
| :--- | :--- | :--- | :--- |
| **Automation** | `ace` | ✅ **Success** | 13 Programs extracted, PDF Queue populated. |
| **Theology** | `teologie`| ❌ **404** | URL structure differs (`/admitere/licenta` not valid). |
| **Mechanics** | `mecanica`| ⚠️ **Timeout** | Server unresponsive (>20s). Needs async/retry tuning. |
| **Electrical** | `ie` | ⚠️ **Timeout** | Subdomain `ie.ucv.ro` unstable during crawl. |
| **Letters** | `litere` | ❌ **404** | Likely uses custom paths (not standardized). |

**Diagnosis**: The UCV infrastructure is **fragile** and **inconsistent**. A synchronous scraper will hang.
**Strategy for Phase 4**: We MUST move to **Asynchronous Fetching** (aiohttp) or aggressive caching with long timeouts for the PDF scraping layer.

---

## 3. The Codebase (Current State)

This is the exact code running in production right now. Use this to design the PDF Parser.

### 3.1 `config.yaml` (The Map)
```yaml
faculties:
  - name: "Facultatea de Automatică..."
    slug: "ace"
    urls: ["https://ace.ucv.ro/admitere/licenta", "https://ace.ucv.ro/admitere/master"]
  ... (11 others)
```

### 3.2 `scraper.py` (The Engine)
```python
    def _extract_from_snapshot(self, html, url, slug, name, pdf_queue):
        # ... (Setup) ...
        
        # Regex Helpers
        RE_SPOTS = re.compile(r'(\d+)\s*loc(?:uri)?\s*(?:la\s+)?buget.*?(\d+)\s*loc(?:uri)?\s*(?:cu\s+)?tax', re.IGNORECASE | re.DOTALL)

        # Domain Tracking
        current_domain = None

        for li in container.find_all("li"):
            text = normalize(li.get_text())
            
            # Domain Header Detection
            if text.lower().startswith("domeniul"):
                current_domain = text.split("Domeniul")[-1].strip(" :")
                continue

            # ... (Signal Filtering) ...

            # PDF Discovery
            pdf_url = find_pdf_link(li)
            if pdf_url:
                program.spots_raw += f" [PDF_REF: {pdf_url}]"
                pdf_queue.append({
                    "program_uid": uid,
                    "pdf_url": pdf_url,
                    "status": "queued"
                })

            # Metadata Append
            if current_domain:
                 program.spots_raw += f" [Domain: {current_domain}]"
```

---

## 4. Request to Thinking Models

We have stabilized the **HTML Layer**. We have the **PDF Queues**.

**The Challenge**:
We have `pdf_queue.json` files containing URLs like `.../locuri_licenta.pdf`.
These PDFs contain the *actual* spots for the Bachelor programs (currently NULL in CSV).

**Prompt**:
"Based on the failure of `mecanica`/`ie` timeouts and the success of `ace`, design a **Robust Phase 4 PDF Scraper**.
1.  **Resilience**: How to handle 20s+ timeouts when downloading 50MB PDFs?
2.  **Parser Stack**: Confirm if `pdfplumber` -> `Table Strategy` is still the best bet for Romanian tables (often messy grids).
3.  **Matching**: How to fuzzy-match `Calculatoare (EN)` (HTML) to `Calc. Eng.` (PDF Row) given the new `[Code: ENG]` helper?"
