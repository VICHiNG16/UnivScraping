from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from execution.models.faculty import Faculty
from execution.models.program import Program
from execution.enrichment.pdf_ranker import PDFTruthRanker
from execution.enrichment.boilerplate import BoilerplateRejector

class UniversityAdapter(ABC):
    """
    Abstract Interface for University-Specific Scraper Logic.
    Decouples the generic BaseScraper from specific HTML structures and rules.
    """
    
    @abstractmethod
    def get_university_slug(self) -> str:
        """Returns unique slug, e.g. 'ucv', 'upb', 'ub'."""
        pass
        
    @abstractmethod
    def get_university_name(self) -> str:
        """Returns human-readable name, e.g. 'Universitatea din Craiova'."""
        pass

    @abstractmethod
    def discover_faculties(self) -> List[Dict[str, Any]]:
        """
        Returns list of faculty configs.
        Format: [{"name": "Faculty Name", "slug": "slug", "urls": ["http..."]}]
        """
        pass

    @abstractmethod
    def get_pdf_ranker(self) -> PDFTruthRanker:
        """Returns configured PDF Ranker for this university."""
        pass

    @abstractmethod
    def get_boilerplate_rejector(self) -> BoilerplateRejector:
        """Returns configured Boilerplate Rejector."""
        pass

    @abstractmethod
    def extract_programs_from_html(self, html: str, url: str, faculty_slug: str) -> List[Program]:
        """
        Parses HTML snapshot and returns list of Program entities.
        Should handle DOM traversal, filtering, and entity creation.
        """
        pass
        
    @abstractmethod
    def extract_pdf_candidates(self, html: str, url: str) -> List[Dict[str, Any]]:
        """
        Extracts PDF links from the page.
        Returns list of {"pdf_url": "...", "link_text": "...", ...}
        """
        pass

    @abstractmethod
    def extract_grade_candidates(self, html: str, url: str) -> List[Dict[str, Any]]:
        """
        Extracts PDF links specifically for Admission Results (Grades).
        """
        pass
        
    @abstractmethod
    def parse_grades(self, pdf_path: str) -> Dict[str, float]:
        """
        Parses a local PDF to extract Last Admission Grades.
        Returns: {"Program Name": 9.50, ...}
        """
        pass
