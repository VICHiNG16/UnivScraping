import pdfplumber
import re
import logging
from typing import List, Dict, Optional, Tuple

from typing import List, Dict, Optional, Tuple
import unicodedata
from execution.enrichment.boilerplate import BoilerplateRejector
from pdf2image import convert_from_path
import pytesseract

logger = logging.getLogger("pdf_parser")

class PDFParser:
    """
    Parser for UCV Admission PDFs (Spots, Taxes, etc.).
    Uses pdfplumber.
    """
    def __init__(self):
        self.logger = logger
        self.boilerplate_rejector = BoilerplateRejector(threshold_ratio=0.6)

    def _ocr_pdf_to_text(self, pdf_path: str) -> str:
        """Fallback: render PDF pages to images and OCR them with Tesseract."""
        try:
            images = convert_from_path(pdf_path, dpi=200)
            texts = []
            for img in images:
                txt = pytesseract.image_to_string(img, lang='ron+eng')  # romanian + english
                texts.append(txt)
            return "\n".join(texts)
        except Exception as e:
            self.logger.error(f"OCR failed for {pdf_path}: {e}")
            return ""

    def extract_spots(self, pdf_path: str) -> List[Dict]:
        """
        Extracts admission spots from a PDF using a Hybrid Strategy.
        1. Try Table Extraction (Structure-based)
        2. Fallback to Text/Regex Extraction (Content-based)
        """
        # Strategy 1: Table Extraction (Best for ACE / Standard Layouts)
        results = self._extract_via_tables(pdf_path)
        if results:
            self.logger.info(f"PDF extraction (Table Strategy) success: {len(results)} rows.")
            return results

        # Strategy 2: Text/Regex Extraction (Best for Agronomie / Lists)
        self.logger.info("Table Strategy returned 0 rows. Attempting Text/Regex Strategy...")
        results = self._extract_via_text(pdf_path)
        if results:
             self.logger.info(f"PDF extraction (Text Strategy) success: {len(results)} rows.")
        else:
             # Strategy 3: OCR Fallback
             self.logger.info("Text Strategy returned 0 rows. Attempting OCR Strategy...")
             try:
                 ocr_text = self._ocr_pdf_to_text(pdf_path)
                 if ocr_text and len(ocr_text) > 100:
                     self.logger.info(f"OCR success ({len(ocr_text)} chars). Re-running Regex Strategy on OCR text...")
                     # Create a virtual page for common logic
                     # We can reuse _extract_via_text logic if we mock pdfplumber behavior or just duplicate the regex run.
                     # Simpler to duplicate regex run here for safety to avoid altering _extract_via_text signature too much.
                     results = self._extract_from_string(ocr_text) 
             except Exception as e:
                 self.logger.error(f"OCR Strategy failed: {e}")

        if not results:
             self.logger.warning("PDF extraction failed with all strategies.")
             
        return results

    def _extract_from_string(self, raw_text: str) -> List[Dict]:
        """Runs the regex extractors on a single string (from OCR)."""
        results = []
        try:
             # Patterns (Duplicate from _extract_via_text for now to avoid refactor complexity)
             name_chars = r"[A-Za-zȘȚĂÂÎșțăâî\d\s\-\(\),\./&]+"
             p1 = re.compile(
                 r'(?:Specializarea|Programul|Domeniul|DISCIPLINA)\s*[:\-]?\s*(' + name_chars + r')[\s\S]{0,300}?Locuri\s*buget\s*[:\-]?\s*(\d+)[\s\S]{0,100}?Locuri\s*tax[aă]\s*[:\-]?\s*(\d+)',
                 re.IGNORECASE
             )
             p2 = re.compile(
                 r'^(' + name_chars + r'?)\s+(\d+)\s*loc.*?buget.*?(\d+)\s*loc.*?tax',
                 re.MULTILINE | re.IGNORECASE
             )
             
             clean_text = self.boilerplate_rejector.clean_text([raw_text])
             clean_text = unicodedata.normalize("NFKD", clean_text)
             clean_text = clean_text.replace("-\n", "").replace("\n", " ")

             for m in p1.finditer(clean_text):
                 results.append({
                     "program_name": m.group(1).strip(),
                     "spots_budget": int(m.group(2)),
                     "spots_tax": int(m.group(3)),
                     "level": "Unknown", 
                     "domain": None,
                     "raw_row": m.group(0)[:100],
                     "page": 1,
                     "source": "ocr"
                 })
             for m in p2.finditer(clean_text):
                 name = m.group(1).strip()
                 if len(name) > 5 and not any(r["program_name"] == name for r in results):
                     results.append({
                         "program_name": name,
                         "spots_budget": int(m.group(2)),
                         "spots_tax": int(m.group(3)),
                         "level": "Unknown",
                         "domain": None,
                         "raw_row": m.group(0),
                         "page": 1,
                         "source": "ocr"
                     })
        except Exception as e:
             self.logger.error(f"OCR Regex failed: {e}")
        return results

    def _extract_via_tables(self, pdf_path: str) -> List[Dict]:
        """Original Table-Based Parse Logic"""
        results = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Metadata Detection (Level)
                detected_level = None

                for page in pdf.pages:
                    # Try to detect level from first valid text
                    if not detected_level:

                        page_text = (page.extract_text() or "").upper()
                        
                        # V9: Smarter Level Detection (Regex on Titles)
                        if re.search(r"ADMITERE.*MASTER", page_text) or re.search(r"STUDII.*MASTER", page_text):
                            detected_level = "Master"
                        elif re.search(r"ADMITERE.*LICEN[TȚ]", page_text) or re.search(r"STUDII.*LICEN[TȚ]", page_text):
                             detected_level = "Licenta"
                        # Fallback: simple presence if no clear title found
                        elif "MASTER" in page_text and "LICEN" not in page_text:
                            detected_level = "Master"
                        elif "LICEN" in page_text and "MASTER" not in page_text:
                            detected_level = "Licenta"
                        # If both present (generic header), look for dominance?
                        elif "LICEN" in page_text and "MASTER" in page_text:
                            # Heuristic: Title usually is "Cifra de scolarizare ... Licenta"
                             if page_text.count("LICEN") > page_text.count("MASTER"):
                                 detected_level = "Licenta"
                             else:
                                 detected_level = "Master"


                    tables = page.extract_tables()
                    for table in tables:

                        # Stacked Header Logic (Scan first 10 rows)
                        header_found = False
                        max_header_row = -1
                        col_map = {"name": -1, "budget": -1, "tax": -1}
                        
                        HEADER_KEYWORDS = ["domeni", "specializ", "program", "buget", "tax", "locuri", "cifra"]

                        for i, row in enumerate(table[:10]):
                            # Normalize row text (list of strings)
                            row_text = []
                            for c in row:
                                txt = str(c).lower().replace("\n", " ").strip() if c else ""
                                row_text.append(txt)
                            
                            joined_row = " ".join(row_text)
                            
                            if any(k in joined_row for k in HEADER_KEYWORDS):
                                header_found = True
                                max_header_row = i
                                

                                # Map Columns (Cumulative - Prefer FIRST match)
                                for c_idx, cell in enumerate(row_text):
                                    cell_norm = cell.replace("ă", "a").replace("ș", "s").replace("ț", "t").replace("â", "a").replace("î", "i")
                                    
                                    if col_map["name"] == -1 and any(k in cell_norm for k in ["domeni", "specializ", "program", "studii"]): 
                                        col_map["name"] = c_idx
                                    
                                    # Budget: Prefer first column that mentions "buget"
                                    if col_map["budget"] == -1 and "buget" in cell_norm and "tax" not in cell_norm: 
                                        col_map["budget"] = c_idx
                                    
                                    # Tax: Prefer first column that mentions "tax"
                                    if col_map["tax"] == -1 and "tax" in cell_norm: 
                                        col_map["tax"] = c_idx


                        # Fallback for name if we found header partially
                        if header_found:
                             if col_map["name"] == -1:
                                 # Guess based on budget/tax position
                                 if col_map["budget"] > 0: col_map["name"] = 0
                                 elif col_map["budget"] == -1: col_map["name"] = 0 # Default

                        # HEURISTIC: Implicit Column Mapping (if explicit headers failed)
                        if col_map["budget"] == -1:
                            # Try to deduce from first valid data row that looks like: Text ... Int ... Int
                            for r_idx, row in enumerate(table):
                                if not row or r_idx < 2: continue # Skip top 2 rows (titles)

                                int_cols = []
                                text_cols = []
                                for idx, cell in enumerate(row):
                                    c_str = str(cell).strip() if cell else ""
                                    if self._parse_int(c_str) is not None:
                                        int_cols.append(idx)
                                    elif len(c_str) > 5 and not any(k in c_str.lower() for k in ["total", "universitatea", "facultatea"]):
                                        text_cols.append(idx)

                                # If we found at least 2 numbers and 1 text, and text is BEFORE numbers
                                if len(int_cols) >= 2 and len(text_cols) >= 1:
                                    if text_cols[0] < int_cols[0]:
                                        col_map["name"] = text_cols[0]
                                        col_map["budget"] = int_cols[0]
                                        col_map["tax"] = int_cols[1]
                                        self.logger.info(f"Implicit Column Map inferred at row {r_idx}: {col_map}")
                                        max_header_row = r_idx - 1
                                        header_found = True
                                        break

                        # Process Data Rows
                        if header_found and max_header_row != -1:
                            self.logger.info(f"Header found at row {max_header_row}. Column Map: {col_map}")
                            extracted_count = 0

                            for row in table[max_header_row+1:]:

                                if not row: continue
                                
                                # Name
                                name_idx = col_map["name"] if col_map["name"] != -1 else 0
                                if name_idx >= len(row): continue
                                name = row[name_idx]
                                if not name: continue
                                name = str(name).strip()
                                
                                name_norm = name.lower().replace("ă", "a").replace("â", "a").replace("î", "i").replace("ș", "s").replace("ț", "t")
                                if len(name) < 3 or any(b in name_norm for b in ["total", "copie", "mentiunea", "original", "secretar", "semnatura", "document", "fiecare"]): continue
                                
                                # Spots
                                budget = None
                                tax = None
                                

                                if col_map["budget"] != -1 and col_map["budget"] < len(row):
                                    budget = self._parse_int(row[col_map["budget"]])
                                
                                if budget is None and not header_found and len(row) > 2:
                                    budget = self._parse_int(row[2])

                                if col_map["tax"] != -1 and col_map["tax"] < len(row):
                                    tax = self._parse_int(row[col_map["tax"]])
                                
                                if tax is None and not header_found and len(row) > 5:
                                    tax = self._parse_int(row[5])

                                # FALLBACK: Greedy Integer Search (if mapped columns failed)
                                if (budget is None and tax is None):
                                    # Find all integers after name column
                                    ints = []
                                    for cell in row[name_idx+1:]:
                                        val = self._parse_int(cell)
                                        if val is not None:
                                            ints.append(val)

                                    if len(ints) >= 1:
                                        budget = ints[0]
                                    if len(ints) >= 2:
                                        tax = ints[1]
                                    if len(ints) > 0:
                                         self.logger.debug(f"Greedy Fallback used for {name}: B={budget}, T={tax}")

                                # Debug Logging
                                self.logger.debug(f"Row[{len(row)}] Name='{name}' B_idx={col_map['budget']} T_idx={col_map['tax']} -> B={budget}, T={tax}")
                                self.logger.debug(f"Row Content: {row}")
                                
                                allow_row = (budget is not None or tax is not None) or (len(name) > 5)

                                
                                if allow_row:
                                    results.append({
                                        "program_name": name,
                                        "spots_budget": budget,
                                        "spots_tax": tax,
                                        "level": detected_level, # V8: Fix Matcher Score
                                        "domain": None, # Future: Extract domain
                                        "raw_row": str(row)
                                    })
                                    extracted_count += 1
        except Exception as e:
            self.logger.error(f"Table extraction failed for {pdf_path}: {e}")
        return results

    def _extract_via_text(self, pdf_path: str) -> List[Dict]:
        """Fallback: Regex patterns on raw text (Layout-agnostic)"""
        results = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                raw_pages = [page.extract_text() or "" for page in pdf.pages]
            
            detected_level = None 
            
            # Patterns (Compile Once)
            name_chars = r"[A-Za-zȘȚĂÂÎșțăâî\d\s\-\(\),\./&]+"
            p1 = re.compile(
                r'(?:Specializarea|Programul|Domeniul|DISCIPLINA)\s*[:\-]?\s*(' + name_chars + r')[\s\S]{0,300}?Locuri\s*buget\s*[:\-]?\s*(\d+)[\s\S]{0,100}?Locuri\s*tax[aă]\s*[:\-]?\s*(\d+)',
                re.IGNORECASE
            )
            p2 = re.compile(
                r'^(' + name_chars + r'?)\s+(\d+)\s*loc.*?buget.*?(\d+)\s*loc.*?tax',
                re.MULTILINE | re.IGNORECASE
            )
            p3 = re.compile(
                r'(?:DISCIPLINA|SPECIALIZAREA|PROGRAMUL)\s*[:\-]\s*([A-ZȘȚĂÂÎ \-]+?)(?:\n|  |$)',
                re.IGNORECASE
            )

            # V8.9: Page-by-Page Processing (Provenance + Isolation)
            for page_idx, raw_text in enumerate(raw_pages):
                if not raw_text: continue
                
                # Clean Boilerplate
                clean_text = self.boilerplate_rejector.clean_text([raw_text])
                
                # Normalize Unicode
                clean_text = unicodedata.normalize("NFKD", clean_text)
                
                # V8.8: Fix Hyphenation (merge split words)
                # "Ingineria\nsistemelor" -> "Ingineria sistemelor"
                # "Tehno-\nlogie" -> "Tehnologie"
                clean_text = clean_text.replace("-\n", "").replace("\n", " ")
                
                # Metadata (Level - primitive check per page or inherited?)
                # Inherit from global detection or re-detect? Re-detect is safer for mixed PDFs.
                page_level = detected_level
                text_upper = clean_text.upper()
                if "MASTER" in text_upper:
                    page_level = "Master"
                elif "LICENTA" in text_upper or "LICENȚĂ" in text_upper:
                    page_level = "Licenta"

                # Apply Pattern 1 (Strongest - Name + Spots)
                for m in p1.finditer(clean_text):
                    results.append({
                        "program_name": m.group(1).strip(),
                        "spots_budget": int(m.group(2)),
                        "spots_tax": int(m.group(3)),
                        "level": page_level, 
                        "domain": None,
                        "raw_row": m.group(0)[:100],
                        "page": page_idx + 1 # Provenance
                    })

                # Apply Pattern 2 (Strong - Line Item)
                for m in p2.finditer(clean_text):
                    name = m.group(1).strip()
                    # Deduplicate locally (per page - or global? global results list)
                    if len(name) > 5 and not any(r["program_name"] == name for r in results):
                        results.append({
                            "program_name": name,
                            "spots_budget": int(m.group(2)),
                            "spots_tax": int(m.group(3)),
                            "level": page_level,
                            "domain": None,
                            "raw_row": m.group(0),
                            "page": page_idx + 1
                        })
                        
                # Apply Pattern 3 (Weakest - Name Only)
                # V8.8: Stricter DISCIPLINA - only if we haven't found spots on this page? 
                # Or just collect everything and let Validator filter.
                for m in p3.finditer(clean_text):
                    name = m.group(1).strip()
                    if len(name) > 5 and "MASTER" not in name.upper() and "AGRONOMIE" not in name.upper():
                         if not any(r["program_name"] == name for r in results):
                            results.append({
                                "program_name": name,
                                "spots_budget": None,
                                "spots_tax": None,
                                "level": page_level, 
                                "domain": None,
                                "raw_row": m.group(0),
                                "page": page_idx + 1
                            })
        
        except Exception as e:
             self.logger.error(f"Text extraction failed for {pdf_path}: {e}")
        
        # V7: Apply Global Blacklist to Text Results too
        final_results = []
        for r in results:
             name = r["program_name"]
             name_norm = name.lower().replace("ă", "a").replace("â", "a").replace("î", "i").replace("ș", "s").replace("ț", "t")
             if not any(b in name_norm for b in ["total", "copie", "mentiunea", "original", "secretar", "semnatura", "document", "fiecare"]):
                 final_results.append(r)

        return final_results

    def _parse_int(self, val) -> Optional[int]:
        if not val: return None
        if isinstance(val, (int, float)): return int(val)
        val = str(val).strip()
        # Remove parentheses notes e.g. "10 (2 rrom)" -> 10
        val = re.split(r'[\(\[\{]', val)[0]
        # Remove non-digits
        val = re.sub(r'[^\d]', '', val)
        if val:
            return int(val)
        return None
