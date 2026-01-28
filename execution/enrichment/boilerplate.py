from typing import List
from collections import Counter
import logging

logger = logging.getLogger("boilerplate")

class BoilerplateRejector:
    """
    Identifies and removes recurring text (headers/footers) from multi-page documents.
    """
    def __init__(self, threshold_ratio: float = 0.6):
        self.threshold_ratio = threshold_ratio # Line must appear in > 60% of pages to be rejected

    def clean_text(self, pages: List[str]) -> str:
        """
        Analyzes pages and returns joined text with boilerplate removal.
        """
        if not pages: return ""
        if len(pages) == 1: return pages[0] # Cannot detect boilerplate on 1 page

        # Normalize lines
        page_lines = []
        all_lines = []
        
        for p in pages:
            lines = [l.strip() for l in p.splitlines() if l.strip()]
            page_lines.append(lines)
            # Use set per page to count occurrence frequency (presence per page)
            all_lines.extend(set(lines))
            
        # Count frequency across pages
        line_counts = Counter(all_lines)
        num_pages = len(pages)
        
        boilerplate_lines = set()
        for line, count in line_counts.items():
            if count / num_pages > self.threshold_ratio:
                boilerplate_lines.add(line)
        
        if boilerplate_lines:
            logger.info(f"Detected {len(boilerplate_lines)} boilerplate lines (Headers/Footers). removing...")
            
        # Reconstruct Text
        cleaned_pages = []
        for p_lines in page_lines:
            clean_lines = [l for l in p_lines if l not in boilerplate_lines]
            cleaned_pages.append("\n".join(clean_lines))
            
        return "\n".join(cleaned_pages)
