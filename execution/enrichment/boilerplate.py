from typing import List, Union
from collections import Counter
import logging
import re

logger = logging.getLogger("boilerplate")

class BoilerplateRejector:
    """
    Iron Dome 2.0: Structural Validation & Boilerplate Removal.
    
    Capabilities:
    1. Cross-Page Fingerprinting (remove headers/footers appearing on > X% of pages).
    2. Structural Heuristics (detect navigation bars, footers, and link clusters).
    """
    def __init__(self, threshold_ratio: float = 0.6):
        self.threshold_ratio = threshold_ratio
        
        # Structural Patterns (Iron Dome)
        self.nav_keywords = ["menu", "home", "contact", "hartă", "search", "faq", "cariere"]
        self.link_density_threshold = 0.8 # If > 80% of text chars are inside <a> tags, it's likely a menu

    def is_structural_garbage(self, tag_node) -> bool:
        """
        Analyzes a BeautifulSoup tag to see if it's navigation, footer, or noise.
        """
        if not tag_node: return False
        
        text = tag_node.get_text(strip=True)
        if not text: return True # Empty is garbage
        
        # 1. Link Density Check (Navigation Bars)
        # Calculate char count inside <a> vs total chars
        links = tag_node.find_all("a", recursive=False) # Only direct children often best for LI
        if not links and tag_node.name == "li":
             # Check if the LI content is essentially just a link
             links = tag_node.find_all("a")
             
        if links:
            link_text_len = sum(len(a.get_text(strip=True)) for a in links)
            total_text_len = len(text)
            if total_text_len > 0:
                density = link_text_len / total_text_len
                if density > self.link_density_threshold and len(text) < 50:
                    # High link density + short text = Nav Item
                    return True

        # 2. Parent Context (e.g., in a <nav> or <div id="footer">)
        parent = tag_node.find_parent(["nav", "footer", "header"])
        if parent: return True
        
        parent_div = tag_node.find_parent("div", {"class": lambda x: x and any(c in x.lower() for c in ["menu", "nav", "footer", "sidebar", "breadcrumb"])})
        if parent_div: return True
        
        # 3. Keyword Heuristics
        text_lower = text.lower()
        if any(k in text_lower for k in self.nav_keywords) and len(text) < 30:
            return True
            
        return False

    def clean_text(self, pages: List[str]) -> str:
        """
        Analyzes pages and returns joined text with boilerplate (repeated lines) removal.
        Useful for concatenated PDF text cleaning.
        """
        if not pages: return ""
        if len(pages) == 1: return pages[0]

        # Normalize lines
        page_lines = []
        all_lines = []
        
        for p in pages:
            lines = [l.strip() for l in p.splitlines() if l.strip()]
            page_lines.append(lines)
            all_lines.extend(set(lines))
            
        # Count frequency
        line_counts = Counter(all_lines)
        num_pages = len(pages)
        
        boilerplate_lines = set()
        for line, count in line_counts.items():
            if count / num_pages > self.threshold_ratio:
                boilerplate_lines.add(line)
        
        if boilerplate_lines:
            logger.info(f"Detected {len(boilerplate_lines)} boilerplate lines (Headers/Footers).")
            
        # Reconstruct
        cleaned_pages = []
        for p_lines in page_lines:
            clean_lines = [l for l in p_lines if l not in boilerplate_lines]
            cleaned_pages.append("\n".join(clean_lines))
            
        return "\n".join(cleaned_pages)
