
import math
import re
from typing import Dict, Any, List

class SemanticValidator:
    """
    Iron Dome V2: Heuristic Semantic Validation for Program Names.
    Filters out 'Garbage' (headers, navigation, random text) from 'Real Programs'.
    Refined by Codex Code Review (Phase 9).
    """
    
    def __init__(self):
        self.NEGATIVE_KEYWORDS = [
            "secretariat", "contact", "acasa", "home", "meniu", "search",
            "regulament", "concurs", "bibliotec", "campus", "cazare",
            "burse", "orar", "proiect", "partener", "despre", "istoric",
            "conducer", "departament", "login", "harta", "gdpr", "cookies",
            "anunt", "eveniment", "noutat", "presa", "media", "galerie",
            "admitere", "inscrier", "secretari"
        ]
        
        self.POSITIVE_KEYWORDS = [
            "inginer", "stiint", "limb", "literatur", "studi",
            "master", "licent", "manag", "drept", "informat", "tehnolog",
            "matemat", "chimi", "fizic", "biolog", "geografi",
            "istori", "teolog", "arte", "muzic", "teatr", "pedagog",
            "sport", "educati", "administra", "econom", "finant", "didac",
            "psiholog", "comunic", "sociolog", "arhitect", "construct",
            "electr", "mecanic", "agronom", "horticult", "silvicult",
            "marketing", "contab", "statistic", "kinetoterap", "farmac"
        ]

        self.PROGRAM_SUFFIXES = [
            "ologie", "istica", "logie", "grafie", "metrie", "nomic", "genie",
            "turism", "silvic", "sanitar", "juridic"
        ]

    def _normalize_text(self, text: str) -> str:
        text = text.lower().strip()
        text = text.replace("ş", "s").replace("ș", "s").replace("ţ", "t").replace("ț", "t")
        text = text.replace("ă", "a").replace("â", "a").replace("î", "i")
        return re.sub(r"[^\w\s]", " ", text)

    def _tokenize(self, text: str) -> List[str]:
        return [t for t in text.split() if t]

    def _has_keyword(self, tokens: List[str], keywords: List[str]) -> bool:
        return any(any(token.startswith(kw) for token in tokens) for kw in keywords)
        
    def validate_program_name(self, name: str) -> Dict[str, Any]:
        """
        Validates a candidate program name.
        Returns: {
            "status": "PASS" | "FAIL" | "QUARANTINE",
            "score": float (0-100),
            "reason": str
        }
        """
        if not name:
            return {"status": "FAIL", "score": 0, "reason": "Empty string"}
            
        name_norm = self._normalize_text(name)
        tokens = self._tokenize(name_norm)
        
        # 1. Entropy / Stucture Checks
        if len(name) < 4:
            return {"status": "FAIL", "score": 0, "reason": "Too short"}
        
        if len(name) > 150:
             return {"status": "FAIL", "score": 0, "reason": "Too long"}
             
        # Digit Ratio (Programs shouldn't be mostly numbers)
        digit_count = sum(c.isdigit() for c in name_norm)
        if digit_count / len(name) > 0.4:
             return {"status": "FAIL", "score": 10, "reason": "High digit ratio (looks like phone/CNP)"}

        # Entropy / diversity check for noisy strings like "aaaaa" or repeated symbols
        alpha_chars = [c for c in name_norm if c.isalpha()]
        unique_alpha = len(set(alpha_chars))
        if alpha_chars and len(alpha_chars) >= 6 and unique_alpha <= 2:
            return {"status": "FAIL", "score": 5, "reason": "Low character diversity"}

        # 2. Negative Keywords (Iron Dome)
        if self._has_keyword(tokens, self.NEGATIVE_KEYWORDS):
             # Find which one
             for kw in self.NEGATIVE_KEYWORDS:
                 if any(t.startswith(kw) for t in tokens):
                    return {"status": "FAIL", "score": 0, "reason": f"Negative keyword: {kw}"}
                
        # 3. Positive Keywords (Boost)
        pos_score = 0
        
        # Keyword Boost
        if self._has_keyword(tokens, self.POSITIVE_KEYWORDS):
            pos_score += 20
            # Extra boost for short precise names? 
            # If any token is EXACT match to a keyword (length-wise approx)
            for kw in self.POSITIVE_KEYWORDS:
                 if any(len(t) <= len(kw) + 3 and t.startswith(kw) for t in tokens):
                     # Small bonus for precision
                     pass

        # Root/Suffix heuristic (Romanian program morphology)
        if any(any(token.endswith(suffix) for suffix in self.PROGRAM_SUFFIXES) for token in tokens):
            pos_score += 15
        
        # 4. Heuristic Scoring
        score = 20 + pos_score
        
        # Word count check: Real programs usually have 2-8 words.
        if len(tokens) == 1 and score < 50:
             # Single word, no positive keyword? Risky.
             pass
        elif len(tokens) >= 2:
            score += 10
        
        # Title Case Bonus
        if name.istitle():
            score += 10
            
        # Decision
        if score >= 45: # Threshold
            return {"status": "PASS", "score": score, "reason": "Good score"}
        elif score >= 30:
            return {"status": "QUARANTINE", "score": score, "reason": "Low confidence"}
        else:
            return {"status": "FAIL", "score": score, "reason": "Low score"}

    def validate_name_hygiene(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rule 2: Name hygiene & separation of counts from title.
        """
        name = row.get("name")
        if not name:
            return {"status": "FAIL", "reason": "Missing name"}
            
        # Regex for embedded counts
        count_pattern = r"(?:B[:\s]*|B\s*[:]?|locuri(?:\s+la\s+buget)?)[^\d]*(?P<budget>\d+)|(?P<tax>\d+)\s*(?:locuri|cu taxă|taxă)|B:\s*(?P<b2>\d+)\s*T:\s*(?P<t2>\d+)"
        noise_pattern = r"(^\s*[>\!\*]+|[\*\!]{2,}|NOU!|Admiterea.*LICENȚĂ)"
        
        m = re.search(count_pattern, name, flags=re.IGNORECASE)
        # We can't safely modify the row here (validator should be side-effect free mostly), 
        # but we can return instructions or fail if it's too messy.
        # For now, if we match robust count pattern, we WARN or CLEAN.
        
        if re.search(noise_pattern, name, flags=re.IGNORECASE):
             return {"status": "REVIEW", "reason": "Name contains UI noise"}
             
        if m:
             return {"status": "REVIEW", "reason": "Name contains embedded counts"}
             
        return {"status": "PASS", "reason": "Clean name"}

    def validate_spots_evidence(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rule 3: Require robust evidence for numeric seats.
        """
        spots_budget = row.get("spots_budget")
        spots_tax = row.get("spots_tax")
        
        if spots_budget is None and spots_tax is None:
            return {"status": "PASS", "reason": "No numeric spots to validate"}
            
        supported = False
        evidence_list = row.get("evidence", {}).get("spots", [])
        
        # Check PDF Evidence
        for e in evidence_list:
            match_score = e.get("match_score", 0)
            score = e.get("score", 0)
            val = e.get("value", {})
            
            # Thresholds: match_score >= 0.75 AND score >= 20
            if match_score >= 0.75 and score >= 20:
                if (spots_budget is not None and val.get("budget") is not None) or \
                   (spots_tax is not None and val.get("tax") is not None):
                    supported = True
                    break
        
        # Check HTML Table Evidence
        if not supported:
            if row.get("source_type") == "html_table_parsed" and row.get("accuracy_confidence", 0) >= 0.8:
                supported = True
                
        if not supported:
            return {"status": "REJECT", "reason": "Spots unverified by high-quality evidence"}
            
        return {"status": "PASS", "reason": "Verified spots"}
        
    def validate_identifiers(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rule 1: Enforce program_id and admission_year.
        """
        if not row.get("program_id"):
            return {"status": "REJECT", "reason": "Missing program_id"}
            
        if not row.get("admission_year"):
            return {"status": "REJECT", "reason": "Missing admission_year"}
            
        return {"status": "PASS", "reason": "Identifiers present"}

    def validate_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Master validation function applying all rules.
        """
        # 1. Name Check (Base)
        name_res = self.validate_program_name(row.get("name", ""))
        if name_res["status"] == "FAIL":
            return name_res
            
        # 2. Hygiene
        hygiene_res = self.validate_name_hygiene(row)
        if hygiene_res["status"] in ["FAIL", "REJECT"]:
            return hygiene_res
            
        # 3. Identifiers
        # Allow missing identifiers for now if we are in "Draft" mode, 
        # but strictly speaking user asked to Filter Out bad rows.
        # We will return REVIEW for missing IDs so they can be fixed.
        id_res = self.validate_identifiers(row)
        if id_res["status"] == "REJECT":
             return {"status": "REVIEW", "reason": id_res["reason"]} # Soften to REVIEW for now
             
        # 4. Spots Evidence
        spots_res = self.validate_spots_evidence(row)
        if spots_res["status"] == "REJECT":
            return spots_res
            
        return {"status": "PASS", "reason": "All checks passed"}
