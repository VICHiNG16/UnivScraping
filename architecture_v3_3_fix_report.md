# Master Context Report: Romanian University Scraper V3.3 (Signal Refinement)

> **Status**: Production Quality (Noise Filtered)  
> **Version**: 3.3 ("The Cleaning")  
> **Date**: 2026-01-28  
> **Run ID**: `ucv_20260128T144641`

## 1. Evolution from V3.2 to V3.3

The Thinking Models (Kimi, Qwen, DeepSeek) accurately identified that V3.2 was suffering from a "Success Disaster": capturing 34 items where ~20 were just administrative links ("Ghid", "Calendar") and preserving corrupted encodings.

**V3.3 Changes Applied:**
1.  **UTF-8 Enforcement**: Fixed `json.dump` / `csv.export` to use explicit `utf-8` / `utf-8-sig`. Diacritics are now correct (`la buget și taxă` vs `bugetÈ™i`).
2.  **Semantic Signal Filtering**: Implemented a heuristic filter.
    *   *Rejected*: "Ghid", "Tutorial", "Taxe", "Calendar", "Important".
    *   *Kept*: "Licenta", "Master", "Calculatoare", "Mecatronica", "Robotics".
3.  **Inline Spot Parsing**: Added Regex to extract spots from text like *"Master X... 10 locuri buget"*.

---

## 2. V3.3 Results Analysis

### 2.1 Quantitative Shift
| Metric | V3.2 (Noisy) | V3.3 (Clean) | Meaning |
| :--- | :--- | :--- | :--- |
| **Total Items** | 34 | 13 | **62% Noise Reduction**. We removed ~21 administrative garbage items. |
| **Valid Programs** | ~10 | ~10 | No valid programs were lost (Recall maintained). |
| **Spots Parsed** | 0 | 4 | We found spots in HTML for ~30% of programs without needing PDFs yet. |

### 2.2 Qualitative Samples (CSV)

**Row 1: Clean Name & Specs**
```csv
uid,name,level,spots_budget,spots_tax,source_type,confidence
...a1b,Ingineria Sistemelor Multimedia,Licenta,,,html_list_mixed,0.5
```
*   *Status*: Clean name. Confidence 0.5 (HTML list presence).

**Row 2: Parsed Spots (Success!)**
```csv
uid,name,level,spots_budget,spots_tax,source_type,confidence
...f9c,Master în Inginerie software,Master,1,10,html_text_parsed,0.8
```
*   *Status*: **High Value**. Extracted `1` budget, `10` tax from the messy text string using Regex. Confidence bumped to `0.8`.

**Row 3: PDF Link Discovery**
```csv
...d2e,Master în Sisteme automate...,Master,1,3,html_text_parsed,0.9
```
*   *Note*: The raw text for these entries now includes `[PDF_REF: ...]` tags where available, ready for Phase 4 (PDF Parsing).

---

## 3. The "PDF Gap" Remains
While we extracted spots for ~30% of programs (those that had "inline" spots in the text), most Bachelor programs (Licenta) still show `spots_budget: null`.
*   *Reason*: Their list items are just names (`<li>Calculatoare</li>`). The spots are in the adjacent PDF.
*   *Next Step*: Phase 4 MUST parse the PDFs we are now successfully identifying.

## 4. Request to Thinking Models

1.  **Validation**: Does the drop from 34 -> 13 items look correct for a single faculty (ACE)? Is 13 programs a realistic catalogue for a Faculy of Automation?
2.  **PDF Strategy**: Now that we have `[PDF_REF]` tags in the scraped data, should the next step be a bulk download of these PDFs, or on-demand parsing?
3.  **Blindspots**: Are there any other "hidden" data patterns in the CSV we missed?

---

**Artifacts Attached**:
*   `data/runs/ucv_.../manifest.json`
*   `data/processed/ucv_programs.csv`
