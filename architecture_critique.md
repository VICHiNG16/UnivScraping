# Architecture Critique & Improvement Plan

## Current Status (v4)
The pipeline successfully navigates the "Bronze" (Snapshot) and part of the "Silver" (Extraction) layers. It correctly discovers faculties and programs from HTML. However, it fails to extract structured data (spots, grades) from the PDFs, which are the primary source of truth for admission statistics.

## Critical Deficiencies

### 1. Missing "Stage B" Integration
The current `BaseScraper.run()` loop downloads PDFs (Stage A) but **never calls the parsing logic** to extract data from them. The `pdf_queue` is processed for downloading, but the resulting files sit in `raw/pdfs/` without being read.
- **Impact**: `spots_budget` and `spots_tax` remain `null` for most programs.

### 2. OCR Dependency Failure
The PDF parser has a fallback to OCR (`pytesseract` + `pdf2image`), but the underlying system dependency `poppler-utils` is missing in the environment.
- **Evidence**: `Unable to get page count. Is poppler installed and in PATH?`
- **Impact**: Scanned PDFs (e.g., Agronomie) return 0 rows/grades.

### 3. Fragile Table Extraction
The `pdfplumber` strategy relies on strict column mapping ("buget", "taxa"). If a table has a different header structure or merged cells, it fails silently.
- **Evidence**: `spots_420c73cd.pdf` returned 0 rows despite containing readable text (verified via debug tool).

### 4. No Spot Parsing Interface
The `UniversityAdapter` interface lacks a standard method for `parse_spots(pdf_path)`. Currently, it only has `parse_grades`. This makes it impossible to generically trigger spot extraction in the base scraper.

## Improvement Plan

### Phase 1: Infrastructure & Interface
1.  **Install Dependencies**: Add `poppler-utils` to the environment.
2.  **Update Interface**: Add `parse_spots(pdf_path) -> List[Dict]` to `UniversityAdapter`.
3.  **Implement in UCV**: Wire up `UCVAdapter.parse_spots` to use `PDFParser.extract_spots`.

### Phase 2: Parser Robustness
1.  **Fix Column Mapping**: Improve `_extract_via_tables` to handle "implicit" columns (e.g., if "Buget" isn't found, check the 2nd numeric column).
2.  **Enable OCR**: Verify OCR works once `poppler` is installed.

### Phase 3: Pipeline Integration
1.  **Enrichment Loop**: Modify `BaseScraper.run()` to:
    - Iterate through downloaded PDFs.
    - Parse them using `adapter.parse_spots()`.
    - Match rows to existing `Program` entities using Fuzzy Matching (`rapidfuzz`).
    - Update and save the Program entities.

### Phase 4: Verification
- Re-run the pipeline and verify that `spots_budget` and `spots_tax` are populated in the JSON output.
