import logging
import re
from pathlib import Path
from typing import List, Dict, Optional
import pdfplumber

logger = logging.getLogger("pdf_ranker")

class PDFTruthRanker:
    """
    Evidence-Driven Ranker for PDF Candidates.
    Stage A: Discovery Scoring (Metadata, URL, Filename)
    Stage B: Evaluation Scoring (Content, Text Density, Rows)
    """
    
    def __init__(self, admission_year: int = 2026):
        self.admission_year = admission_year
        self.doc_types = {
            "SPOTS": ["cifra", "locuri", "capacitate"],
            "RESULTS": ["rezultate", "medii", "admis", "respins", "ierarhie"],
            "GUIDE": ["ghid", "metodologie", "regulament"],
            "EXAM": ["tematica", "subiecte", "grile", "disciplina"],
            "CALENDAR": ["calendar", "programare", "data", "perioada"]
        }

    def rank_candidates(self, candidates: List[Dict], target_type: str = "SPOTS") -> List[Dict]:
        """
        Stage A: Initial ranking based on metadata only.
        target_type: "SPOTS" or "RESULTS" (boosts respective keywords)
        """
        for cand in candidates:
            score = 0.0
            text = (cand.get("link_text") or "").lower()
            url = (cand.get("pdf_url") or cand.get("url") or "").lower()
            
            # 1. Year Relevance
            if str(self.admission_year) in text or str(self.admission_year) in url:
                score += 10.0
            elif str(self.admission_year - 1) in text or str(self.admission_year - 1) in url:
                 if target_type == "RESULTS":
                     score += 8.0 # Results might be from previous year!
                 else:
                     score += 5.0
            
            # 2. Target Type Keywords (Boost)
            if target_type in self.doc_types:
                keywords = self.doc_types[target_type]
                if any(k in text for k in keywords) or any(k in url for k in keywords):
                    score += 15.0 # Strong boost for matching intent
            
            # 3. Negative signals (Context dependent)
            # If looking for SPOTS, penalize RESULTS/GUIDE
            # If looking for RESULTS, penalize SPOTS/GUIDE
            
            negative_types = []
            if target_type == "SPOTS":
                 negative_types = self.doc_types["GUIDE"] + self.doc_types["EXAM"] + self.doc_types["RESULTS"]
            elif target_type == "RESULTS":
                 negative_types = self.doc_types["GUIDE"] + self.doc_types["EXAM"] + self.doc_types["SPOTS"]
            
            if any(k in text for k in negative_types):
                score -= 10.0

            if any(k in text for k in self.doc_types["CALENDAR"]):
                score -= 20.0
                
            cand["stage_a_score"] = score
        
        # Sort descending
        return sorted(candidates, key=lambda x: x["stage_a_score"], reverse=True)

    def evaluate_content(self, pdf_path: str) -> Dict:
        """
        Stage B: Deep inspection of PDF content.
        Returns metrics and a 'content_score'.
        """
        metrics = {
            "page_count": 0,
            "text_density": 0.0,
            "has_table": False,
            "rows_with_numbers": 0,
            "detected_year": None,
            "content_score": 0.0
        }
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                metrics["page_count"] = len(pdf.pages)
                if not pdf.pages:
                    return metrics

                # Scan first 2 pages max
                sample_text = ""
                for i, page in enumerate(pdf.pages[:2]):
                    text = page.extract_text() or ""
                    sample_text += text
                    
                    if page.extract_tables():
                        metrics["has_table"] = True
                
                # Metrics
                char_count = len(sample_text)
                metrics["text_density"] = char_count / max(1, min(metrics["page_count"], 2))
                
                # Year Detection
                if str(self.admission_year) in sample_text:
                    metrics["detected_year"] = self.admission_year
                
                # Spot Detection (Regex scan for numbers near 'buget'/'tax')
                # Simple check: how many lines look like "Name ... 12 ... 34"
                lines_with_spots = len(re.findall(r'\d+\s+(?:loc|buget|tax)', sample_text, re.IGNORECASE))
                metrics["rows_with_numbers"] = lines_with_spots

                # Scoring
                score = 0.0
                
                # Scanned vs Digital
                if metrics["text_density"] < 50:
                    score -= 10.0 # Likely scanned image
                else:
                    score += 5.0
                
                # Evidence of Spots
                if metrics["rows_with_numbers"] > 0:
                    score += 10.0 + min(metrics["rows_with_numbers"], 10) # Max 20 pts
                
                if metrics["has_table"]:
                    score += 5.0

                metrics["content_score"] = score

        except Exception as e:
            logger.error(f"Failed to evaluate content for {pdf_path}: {e}")
            
        return metrics
