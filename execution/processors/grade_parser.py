import logging
import re
import statistics
import pdfplumber
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger("grade_parser")

class LastAdmissionGradeParser:
    """
    Parses 'Results' PDFs to extract the Minimum Admission Grade (Last Admitted).
    Privacy-Safe: Does NOT store candidate names. Only aggregates.
    """
    
    def __init__(self):
        self.min_samples = 3 # Require at least 3 grades to trust the min
        
    def extract_min_grades(self, pdf_path: str) -> Dict[str, float]:
        """
        Returns { "Program Name": min_grade }
        """
        results = {}
        processed_programs = {} # name -> list of grades
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    # 1. Text Strategy (for explicit "Ultima medie" lines)
                    text = page.extract_text() or ""
                    explicit = self._scan_explicit_minima(text)
                    if explicit:
                        results.update(explicit)
                        continue # If explicit found on page, rely on it? Or mix?
                        
                    # 2. Table Strategy (Scan columns for "Medie")
                    tables = page.extract_tables()
                    for table in tables:
                        self._process_table(table, processed_programs)
                        
        except Exception as e:
            logger.error(f"Error parsing grades from {pdf_path}: {e}")
            return {}

        # Aggregate processed programs
        for name, grades in processed_programs.items():
            if len(grades) >= self.min_samples:
                clean_grades = [g for g in grades if 5.0 <= g <= 10.0]
                if clean_grades:
                    results[name] = min(clean_grades)
                    logger.info(f"Extracted Min Grade for '{name}': {min(clean_grades)} (from {len(clean_grades)} candidates)")
            else:
                logger.debug(f"Skipping '{name}': Not enough samples ({len(grades)})")

        return results

    def _scan_explicit_minima(self, text: str) -> Dict[str, float]:
        """
        Scans for sentences like "Ultima medie la Informatica: 9.50"
        """
        found = {}
        # Regex for explicit declarations (rare but valuable)
        # e.g. "Ultima medie de admitere: 8.50"
        # Context is hard without Program Name anchor.
        # Skip for now unless structured.
        return found
        
    def _process_table(self, table: List[List[str]], accumulator: Dict[str, List[float]]):
        """
        Identifies "Medie" column and extracts numbers.
        Associates with Program Name if present in row or header.
        """
        if not table: return
        
        headers = table[0]
        grade_col_idx = -1
        name_col_idx = -1
        
        # Detect Columns
        for i, cell in enumerate(headers):
            if not cell: continue
            c = str(cell).lower()
            if "medie" in c or "nota" in c or "concurs" in c:
                grade_col_idx = i
            if "specializ" in c or "program" in c or "domeniu" in c:
                name_col_idx = i
                
        if grade_col_idx == -1: return
        
        current_program = "Unknown" # If name column missing, might be PDF-level program?
        # TODO: Pass PDF context (program name from filename/metadata)
        
        for row in table[1:]:
            if len(row) <= grade_col_idx: continue
            
            # Update Program context if column exists
            if name_col_idx != -1 and len(row) > name_col_idx:
                val = row[name_col_idx]
                if val and len(str(val)) > 5:
                    current_program = str(val).strip().replace("\n", " ")
            
            # Extract Grade
            raw_grade = row[grade_col_idx]
            grade = self._parse_grade(raw_grade)
            
            if grade:
                if current_program not in accumulator:
                    accumulator[current_program] = []
                accumulator[current_program].append(grade)

    def _parse_grade(self, filtered_text: Optional[str]) -> Optional[float]:
        if not filtered_text: return None
        try:
            # Handle "9,50" -> 9.50
            t = str(filtered_text).replace(",", ".").strip()
            val = float(t)
            if 1.0 <= val <= 10.0:
                return val
        except ValueError:
            pass
        return None
