import unicodedata

class RomanianTextNormalizer:
    """
    Normalizes Romanian text, handling diacritics and common inconsistencies.
    """
    @staticmethod
    def normalize(text: str) -> str:
        if not text:
            return ""
        
        # Normalize Unicode (NFC)
        text = unicodedata.normalize('NFC', text)
        
        # Standardize diacritics (Comma vs Cedilla)
        # Romanian needs comma-below (ș, ț), roughly s+comma encoded as \u0219
        # Many sites use cedilla (ş, ţ) \u015f which is Turkish/Legacy.
        # We enforce comma-below for correctness, or maybe ASCII for slugging?
        # Let's enforce standard Romanian diacritics for display.
        
        replacements = {
            'ş': 'ș', 'Ş': 'Ș',
            'ţ': 'ț', 'Ţ': 'Ț'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        return text.strip()
