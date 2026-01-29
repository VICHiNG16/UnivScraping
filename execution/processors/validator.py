
import math
import re
from typing import Dict, Any, List

class SemanticValidator:
    """
    Iron Dome V2: Heuristic Semantic Validation for Program Names.
    Filters out 'Garbage' (headers, navigation, random text) from 'Real Programs'.
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
        for kw in self.NEGATIVE_KEYWORDS:
            if any(token.startswith(kw) for token in tokens):
                return {"status": "FAIL", "score": 0, "reason": f"Negative keyword: {kw}"}
                
        # 3. Positive Keywords (Boost)
        pos_score = 0
        for kw in self.POSITIVE_KEYWORDS:
            if any(token.startswith(kw) for token in tokens):
                pos_score += 20
                if len(name_norm) <= len(kw) + 3:
                    pos_score += 15

        # Root/Suffix heuristic (Romanian program morphology)
        if any(any(token.endswith(suffix) for suffix in self.PROGRAM_SUFFIXES) for token in tokens):
            pos_score += 10
        
        # 4. Heuristic Scoring
        # Base score starts low, needs positive signal
        score = 20 + pos_score
        
        # Word count check: Real programs usually have 2-8 words.
        # "Informatica" (1 word) is valid.
        # "Bun venit la facultatea noastra" (6 words) is invalid.
        words = name.split()
        if len(words) == 1 and score < 50:
             # Single word, no positive keyword? Risky.
             # e.g. "Diverse" -> FAIL
             pass
        elif len(words) >= 2:
            # Multi-word names are more likely to be real programs
            score += 10
        
        # Title Case Bonus
        # "Ingineria Sistemelor" vs "ingineria sistemelor" vs "CONTACT"
        if name.istitle():
            score += 10
            
        # Decision
        if score >= 45: # Lowered from 50
            return {"status": "PASS", "score": score, "reason": "Good score"}
        elif score >= 30:
            return {"status": "QUARANTINE", "score": score, "reason": "Low confidence"}
        else:
            return {"status": "FAIL", "score": score, "reason": "Low score"}
