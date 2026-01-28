import pdfplumber
import re
import logging
from typing import List, Dict, Optional, Tuple

from typing import List, Dict, Optional, Tuple
import unicodedata
from execution.enrichment.boilerplate import BoilerplateRejector

logger = logging.getLogger("pdf_parser")

class PDFParser:
    """
    Parser for UCV Admission PDFs (Spots, Taxes, etc.).
    Uses pdfplumber.
    """
    def __init__(self):
        self.logger = logger
        self.boilerplate_rejector = BoilerplateRejector(threshold_ratio=0.6)

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
             self.logger.warning("PDF extraction failed with both strategies.")
             
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
                        if "MASTER" in page_text:
                            detected_level = "Master"
                        elif "LICENTA" in page_text or "LICENȚĂ" in page_text:
                            detected_level = "Licenta"

                    tables = page.extract_tables()
                    for table in tables:
                        # Heuristic: Find header row
                        header_idx = -1
                        col_map = {"name": -1, "budget": -1, "tax": -1}
                        
                        for i, row in enumerate(table):
                            # Normalize row text
                            row_text = []
                            for c in row:
                                if c:
                                    # Normalize unicode (e.g. Ș -> S) for easier matching
                                    # But keep original for extraction if needed? No, standardizing is safer for keywords.
                                    txt = str(c).lower().replace("\n", " ").strip()
                                    # Simple accent stripping for keywords
                                    # (We don't need full normalization for the content, just the checks)
                                    row_text.append(txt)
                                else:
                                    row_text.append("")
                            
                            # Join for broader check
                            joined_row = " ".join(row_text)
                            
                            # Detect Header
                            # Expanded keywords for Agronomie ("Studii", "Cifra", "Locuri")
                            HEADER_KEYWORDS = ["domeni", "specializ", "program", "studii", "buget", "tax", "cifra", "locuri"]
                            
                            if any(k in joined_row for k in HEADER_KEYWORDS):
                                header_idx = i
                                # Map Columns
                                for c_idx, cell in enumerate(row_text):
                                    cell_norm = cell.replace("ă", "a").replace("ș", "s").replace("ț", "t").replace("â", "a").replace("î", "i")
                                    
                                    if any(k in cell_norm for k in ["domeni", "specializ", "program", "studii"]): 
                                        col_map["name"] = c_idx
                                    if "buget" in cell_norm and "tax" not in cell_norm: 
                                        col_map["budget"] = c_idx
                                    if "tax" in cell_norm: 
                                        col_map["tax"] = c_idx
                                
                                break
                        
                        # Process Data Rows
                        if header_idx != -1:
                            extracted_count = 0
                            for row in table[header_idx+1:]:
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
                                
                                if budget is None and len(row) > 2:
                                    budget = self._parse_int(row[2])

                                if col_map["tax"] != -1 and col_map["tax"] < len(row):
                                    tax = self._parse_int(row[col_map["tax"]])
                                
                                if tax is None and len(row) > 5:
                                    tax = self._parse_int(row[5])
                                
                                # Allow extraction if we have a name (even if spots are missing, for synthesis)
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
