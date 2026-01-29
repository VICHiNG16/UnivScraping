# GPT-5.2 Pro Consultation: Scalability Architecture

**Role**: You are the Senior System Architect advising on a Python-based university scraping platform.

**Current State**:
- We have a working pipeline for **1 University** (University of Craiova - "UCV") with multiple faculties.
- **Tech Stack**:
    - `crawl4ai` (HTML) + `pdfplumber` (PDF)
    - `pydantic` models (strict schema)
    - `rapidfuzz` (fuzzy matching validation)
    - `DataFusionEngine` (merges HTML & PDF sources)
- **Architecture**:
    - `UniversityAdapter` interface (see below) is designed to standardize scraping across different sites.
    - We currently instantiate `UCVAdapter` which implements this interface.

**The Challenge**:
We need to scale from **1 University** to **50+ Universities** (approx. 200+ faculties).
Each university has unique layouts, inconsistent PDF formats, and different "spots" terminologies.

**Specific Questions for You**:
1.  **Factory Pattern**: How should we structure the project to manage 50+ adapter files? (e.g., `execution/scrapers/{uni_slug}/adapter.py` vs a plugin system?)
2.  **Configuration vs Code**: Should we try to move selector logic (CSS/XPath) into YAML config files to minimize code, or stay with Python classes for flexibility?
3.  **Resilience**: With 50 concurrent scrapers (or sequential), how do we handle shared resources (browser instances) and rate limiting without a complex queueing infrastructure (like Celery/Redis) if we want to keep it simple?
4.  **Adapter Interface Review**: Please review the provided `UniversityAdapter` interface. Is it abstract enough? Are we missing methods for "Pagination" or "Authentication" that might pop up later?

**Context Code**:

```python
# execution/scrapers/adapter_interface.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any

class UniversityAdapter(ABC):
    """
    Standard interface for all University scrapers.
    Ensures that the Main Pipeline can treat UCV, UPB, UBB identicaly.
    """

    @abstractmethod
    def get_faculties(self) -> List[Dict[str, str]]:
        """
        Returns a list of faculties to scrape.
        [{ "name": "Automatica", "slug": "ac", "url": "..." }]
        """
        pass

    @abstractmethod
    def scrape_faculty_structure(self, faculty_slug: str, url: str) -> List[Dict[str, Any]]:
        """
        Scrapes the HTML structure to find programs (Bachelor/Master)
        and potential PDF links.
        """
        pass

    @abstractmethod
    def get_pdf_links(self, faculty_slug: str, soup: Any) -> List[str]:
        """
        Extracts relevant PDF links (spots, admission info) from the page.
        """
        pass
```

**Output Desired**:
A strategic roadmap for the "Scalability Phase" and a critique of the Interface.
