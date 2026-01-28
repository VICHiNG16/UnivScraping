# Master Context Report: Romanian University Scraper V3.5
> **State**: Production Ready (HTML Layer)  
> **Date**: 2026-01-28  
> **Version**: 3.5 (The "Zero-Noise" Release)  
> **Docs**: [Original Plan](architecture_v3_2_report.md) | [V3.3 Fixes](architecture_v3_3_fix_report.md)

This document is the **Single Source of Truth** for the Thinking AIs (DeepSeek, Qwen, Kimi). It details the complete architectural journey from a broken Pilot to a forensic-grade Data Pipeline, including every bug encountered and the exact code used to fix it.

---

## 1. Executive Summary

We have successfully engineered a **Forensic Web Scraper** for the University of Craiova (UCV).
*   **Input**: `https://ace.ucv.ro/admitere/licenta` (and Master).
*   **Output**: Clean, UTF-8 CSV with 13 Valid Programs (filtered from 34 noise items).
*   **Capabilities**:
    *   **Double-Encoding Repair**: Automatically fixes "Mojibake" (ISO-8859-1 interpretation of UTF-8).
    *   **Semantic Filtering**: Distinguishes "Computer Science" (Program) from "Student Guide" (Noise).
    *   **Inline Spot Parsing**: Extracts "10 budget / 5 tax" from unstructured text blocks.
    *   **PDF Link Discovery**: Tags programs with `[PDF_REF]` when data is missing from HTML.

**Current Blocker**: The "PDF Gap". 70% of programs (mostly Licenta) list their spots *only* in PDFs. We have the Links; we need a Phase 4 Strategy.

---

## 2. Architecture Evolution (The "Fix Log")

### V3.1: The Naive Pilot
*   **Status**: *Broken*
*   **Issues**:
    *   Captured "Ghid", "Calendar" as programs.
    *   Unstable UIDs (hashes changed every run).
    *   Overwrote snapshots (Lost data history).

### V3.2: Forensics & Stability
*   **Fixes**:
    *   **UID System**: `provenance.py` now uses `canonical_url + normalized_name`.
    *   **Snapshotting**: Uses `timestamp_urlhash.html` to prevent overwrites.
    *   **Manifests**: Generates `manifest.json` for every run.

### V3.3: Signal Refinement
*   **Fixes**:
    *   **Noise Filter**: Added `NOISE_KEYWORDS` (e.g., "taxe", "tutorial") to reject administrative links.
    *   **Regex Engine**: Added `RE_SPOTS` to parse inline text strings.
    *   **Result**: Reduced 34 rubbish items to 13 valid programs.

### V3.4: The Encoding (Mojibake) Fix
*   **Bug**: CSV showed `MecatronicÄ Èi`.
*   **Root Cause**: `requests` defaulted to ISO-8859-1 because the server sent no charset. The bytes were UTF-8.
*   **Code Fix (`scraper.py`)**:
    ```python
    # Heuristic: If content has "Ä" (C4) but no "ă", it's likely Latin-1 misinterpretation of UTF-8.
    if "Ä" in resp.text and "ă" not in resp.text:
         resp.encoding = 'utf-8'
    ```

### V3.5: The Typography (Spacing) Fix
*   **Bug**: CSV showed `Master înInginerie`.
*   **Root Cause**: `BeautifulSoup.get_text(strip=True)` merges adjacent inline tags: `Master în<b>Inginerie</b>` -> `Master înInginerie`.
*   **Code Fix**:
    ```python
    # Inject space separator between tags
    raw_text = li.get_text(separator=" ", strip=True)
    # Normalize multiple spaces back to one
    text = re.sub(r'\s+', ' ', raw_text).strip()
    ```

---

## 3. Technical Implementation Details

### 3.1 The "Forensic" Scraper Class (`UCVScraper`)
Located in: `execution/scrapers/ucv/scraper.py`

**Key Components:**

1.  **Noise Filters**:
    ```python
    NOISE_KEYWORDS = ["ghid", "tutorial", "aici", "documente", "taxe", "înscriere", 
                      "calendar", "confirmare", "prelucrare", "date personale", "important"]
    ```

2.  **Spot Parsing Regex**:
    ```python
    # Capture Group 1: Budget, Group 2: Tax
    RE_SPOTS = re.compile(r'(\d+)\s*loc(?:uri)?\s*(?:la\s+)?buget.*?(\d+)\s*loc(?:uri)?\s*(?:cu\s+)?tax', re.IGNORECASE | re.DOTALL)
    ```

3.  **PDF Discovery Logic**:
    ```python
    # Look for PDF link inside LI or immediately following it
    a_tag = li.find("a", href=lambda h: h and h.lower().endswith(".pdf"))
    if not a_tag:
        sibling_a = li.find_next_sibling("a", href=lambda h: h and h.lower().endswith(".pdf"))
    
    if pdf_url:
        program.spots_raw += f" [PDF_REF: {pdf_url}]"  # <-- The Breadcrumb for Phase 4
    ```

### 3.2 The Infrastructure Layer
Located in: `execution/base/scraper_base.py`

*   **Bronze Layer**: Saves `data/runs/{run_id}/raw/{slug}/{timestamp}_{hash}_snapshot.html`.
*   **Silver Layer**: Saves `data/runs/{run_id}/raw/{slug}/programs/{uid}.json`.
*   **Persistence**: `json.dump(ensure_ascii=False)` to respect Romanian characters.

---

## 4. Current Data Status (V3.5 Output)

**Sample Row (Master - High Confidence):**
```csv
uid: ...e85c
name: "Master în Tehnologii informatice în ingineria sistemelor"
level: "Master"
spots_budget: 12
spots_tax: 5
source_type: "html_text_parsed"
confidence: 0.8  <-- High because strict regex matched
provenance: "Parsed from '...12 locuri la buget și 5 locuri cu taxă;'"
```

**Sample Row (Licenta - The "PDF Gap"):**
```csv
uid: ...722c
name: "Calculatoare (în limba engleză)"
level: "Licenta"
spots_budget: NULL
spots_tax: NULL
source_type: "html_list_mixed"
confidence: 0.5  <-- Low because only name was found
spots_raw: "Calculatoare (în limba engleză) [PDF_REF: /admitere/licenta/Metodologie.pdf]"
```
*Note: The actual specific spots PDF is often buried in a generic "Metodologie" link or a nearby table we haven't parsed yet.*

---

## 5. Strategic Questions for Thinking Models

We have perfected the HTML extraction. Now we face the **Format Barrier**.

1.  **Phase 4 Strategy**:
    *   Should we implement a `PDFScraper` class that inherits from `BaseScraper`?
    *   Or check the `[PDF_REF]` tags during the *Silver* phase and download them on demand?

2.  **PDF Parsing Technology**:
    *   **Option A**: `pypdf` / `pdfminer` (Text-based). Fast, cheap. Good for "native" PDFs.
    *   **Option B**: `camelot` (Table-based). Good for tabular data.
    *   **Option C**: OCR (scan-based). Likely needed for older Romanian docs.
    *   **Recommendation**: Which library stack is best for Romanian academic tables?

3.  **Fuzzy Matching**:
    *   The PDF will list "Calculatoare - Engleza" (Short name).
    *   The HTML has "Calculatoare (în limba engleză)" (Long name).
    *   What is the most robust Python mechanism to join these datasets? (`rapidfuzz`? Levenshtein?)

4.  **Scaling**:
    *   Is the current `manifest.json` structure sufficient to track "PDFs downloaded vs parsed"?

---

**Artifacts Available for Review:**
*   `execution/scrapers/ucv/scraper.py` (The V3.5 Logic)
*   `data/processed/ucv_programs.csv` (The V3.5 Output)
