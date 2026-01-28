# Master Context Report: Romanian University Scraper V3.4 (UTF-8 Fixed)

> **Status**: Production Quality (Encoding Fixed)  
> **Version**: 3.4 ("The Mojibake Fix")  
> **Date**: 2026-01-28  
> **Run ID**: `ucv_20260128T144913`

## 1. Evolution from V3.3 to V3.4

The user flagged a critical data quality issue: `MecatronicÄ Èi` instead of `Mecatronică și`. This was a "Double Encoding" issue where `requests` defaulted to ISO-8859-1 for UCV's server, but the content interpreted physically as UTF-8.

**V3.4 Changes Applied:**
1.  **Strict Fetch Encoding**: Patched `UCVScraper` to check `response.apparent_encoding` and heuristically force UTF-8 if it detects "Ä" (Mojibake for "ă") but no actual "ă".
2.  **Persistence Layer**: `scraper_base` now uses `ensure_ascii=False` (JSON) and `utf-8-sig` (CSV).

---

## 2. V3.4 Results Quality

### Encoding Verification (Line 9)
**Old (Broken):**
`MecatronicÄ Èi RoboticÄ`

**New (Fixed):**
`Mecatronică și Robotică`

### Data Stats
*   **Programs**: 13 (Clean filtered set)
*   **Encoding**: Perfect Romanian diacritics
*   **Spots**: 4 programs with inline spots parsed

---

## 3. Request to Thinking Models

1.  **Architecture Check**: Is the explicit "Encoding Heuristic" (checking for "Ä" vs "ă") a safe pattern for Romanian scraping at scale? Or is there a cleaner `requests` configuration?
2.  **Next Step**: With clean data and stable structure, are we ready for **Phase 4 (PDF Parser)**?
3.  **PDF Complexity**: Given that 70% of programs still have NULL spots (because they are in PDFs), please provide the **Schema/Prompt** needed to extract these spots from the PDFs. See rows with `[PDF_REF: ...]` in the RAW data.
