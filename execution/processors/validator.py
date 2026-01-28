
import re
import math
from typing import Dict, Any, List

class SemanticValidator:
    """
    Iron Dome V2: Heuristic Semantic Validation for Program Names.
    Filters out 'Garbage' (headers, navigation, random text) from 'Real Programs'.
    """
    
    def __init__(self):
        self.NEGATIVE_KEYWORDS = [
            "secretariat", "contact", "acasa", "home", "meniu", "search", 
            "regulament", "concurs", "biblioteca", "campus", "cazare", 
            "burse", "orar", "proiecte", "parteneri", "despre", "istoric", 
            "conducere", "departamente", "login", "harta", "gdpr", "cookies",
            "anunturi", "evenimente", "noutati", "presă", "media", "galerie"
        ]
        
        self.POSITIVE_KEYWORDS = [
            "inginer", "stiint", "limb", "literatur", "studi", 
            "master", "licent", "manag", "drept", "informat", "tehnolog",
            "matemat", "chimi", "fizic", "biolog", "geografi", 
            "matemat", "chimi", "fizic", "biolog", "geografi",
            "istori", "teolog", "art", "muzic", "teatr", "pedagog",
            "sport", "educati", "administra", "econom", "finant", "didac"
        ]
        
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
            
        name_lower = name.lower().strip()
        
        # 1. Entropy / Stucture Checks
        if len(name) < 4:
            return {"status": "FAIL", "score": 0, "reason": "Too short"}
        
        if len(name) > 150:
             return {"status": "FAIL", "score": 0, "reason": "Too long"}
             
        # Digit Ratio (Programs shouldn't be mostly numbers)
        digit_count = sum(c.isdigit() for c in name)
        if digit_count / len(name) > 0.4:
             return {"status": "FAIL", "score": 10, "reason": "High digit ratio (looks like phone/CNP)"}

        # 2. Negative Keywords (Iron Dome)
        for kw in self.NEGATIVE_KEYWORDS:
            if kw in name_lower:
                # "Secretariat" is fatal. "Contact" is fatal.
                # Check for context: "Secretariatul Facultatii" vs "Secretariat si Administratie"
                return {"status": "FAIL", "score": 0, "reason": f"Negative keyword: {kw}"}
                
        # 3. Positive Keywords (Boost)
        pos_score = 0
        for kw in self.POSITIVE_KEYWORDS:
            if kw in name_lower:
                pos_score += 20
                # If name IS the keyword (nearly), extra boost
                # e.g. "Informatica" vs "Facultatea de Informatica"
                if len(name_lower) <= len(kw) + 3:
                     pos_score += 15
        
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
