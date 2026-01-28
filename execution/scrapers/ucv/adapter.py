
import yaml
import re
import datetime
from typing import List, Dict, Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import unicodedata

from execution.scrapers.adapter_interface import UniversityAdapter
from execution.models.program import Program
from execution.models.provenance import ProvenanceMixin
from execution.enrichment.pdf_ranker import PDFTruthRanker
from execution.enrichment.boilerplate import BoilerplateRejector
from execution.processors.grade_parser import LastAdmissionGradeParser

class UCVAdapter(UniversityAdapter):
    def __init__(self):
        self.config = self._load_config()
        self.ranker = PDFTruthRanker(admission_year=datetime.datetime.now().year)
        self.boilerplate_rejector = BoilerplateRejector()
        self.grade_parser = LastAdmissionGradeParser()
        
    def _load_config(self) -> Dict[str, Any]:
        try:
            with open("execution/scrapers/ucv/config.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                return cfg
        except FileNotFoundError:
            return {"faculties": []}

    def get_university_slug(self) -> str:
        return "ucv"

    def get_university_name(self) -> str:
        return "Universitatea din Craiova"

    def discover_faculties(self) -> List[Dict[str, Any]]:
        return self.config.get("faculties", [])

    def get_pdf_ranker(self) -> PDFTruthRanker:
        return self.ranker

    def get_boilerplate_rejector(self) -> BoilerplateRejector:
        return self.boilerplate_rejector

    def extract_pdf_candidates(self, html: str, url: str) -> List[Dict[str, Any]]:
        candidates = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Generic container for UCV
        container = soup.find("div", id="continut_standard") or soup.find("div", id="main_content") or soup
        
        for link in container.find_all("a", href=True):
            href = link["href"].strip()
            if href.lower().endswith(".pdf"):
                full_url = urljoin(url, href)
                candidates.append({
                    "pdf_url": full_url,
                    "link_text": link.get_text(strip=True),
                    "source_url": url,
                    "discovered_at": datetime.datetime.now().isoformat()
                })
        return candidates

    def extract_programs_from_html(self, html: str, url: str, faculty_slug: str) -> List[Program]:
        programs = []
        
        # PDF-Only Faculties Strategy
        PDF_ONLY_FACULTIES = ["agronomie"] 
        if faculty_slug in PDF_ONLY_FACULTIES:
            return [] # No HTML programs for these
            
        soup = BeautifulSoup(html, "html.parser")
        container = soup.find("div", id="continut_standard") or soup.find("div", id="main_content") or soup
        
        # Regex Helpers
        RE_SPOTS = re.compile(r'(\d+)\s*loc(?:uri)?\s*(?:la\s+)?buget.*?(\d+)\s*loc(?:uri)?\s*(?:cu\s+)?tax', re.IGNORECASE | re.DOTALL)
        RE_BUDGET = re.compile(r'(\d+)\s*loc(?:uri)?\s*(?:la\s+)?buget', re.IGNORECASE)
        RE_TAX = re.compile(r'(\d+)\s*loc(?:uri)?\s*(?:cu\s+)?tax', re.IGNORECASE)
        
        NOISE_KEYWORDS = ["ghid", "tutorial", "documente", "taxe", "înscriere", "calendar", "confirmare"]
        PROGRAM_KEYWORDS = ["licență", "master", "doctorat", "calculatoare", "inginerie", "drept", "litere"]

        current_domain = None
        
        for ul in container.find_all("ul"):
            for li in ul.find_all("li"):
                raw_text = li.get_text(separator=" ", strip=True)
                text = re.sub(r'\s+', ' ', raw_text).strip()
                if not text: continue
                
                # Simple Domain Context
                if text.lower().startswith("domeniul"):
                    current_domain = text.split("Domeniul")[-1].strip(" :")
                    continue

                # --- FILTERS ---
                has_spots = RE_BUDGET.search(text) or RE_TAX.search(text)
                is_noise = any(kw in text.lower() for kw in NOISE_KEYWORDS)
                
                # Boilerplate/Navigation Filtering (Iron Dome Lite - pending full migration)
                BLACKLIST_PATTERNS = [
                    r'Search', r'Button', r'Menu', r'Aici', r'Contact', 
                    r'^Tel:', r'^Fax:', r'^Str\.', r'^Bulevardul', r'^Piața',
                    r'www\.', r'http', r'@[a-z]+\.ro', 
                    r'Căminul', r'Studentesc',  r'Burse',
                    r'Evenimente', r'Strategia', r'Anunțuri', r'Orar', r'Fișe', r'Planuri',
                    r'Declaratii', r'Evaluare', r'Structura', r'Conducere', r'Secretariat',
                    r'Metodologii', r'Rezultate', r'Chestionar', r'Cazare', r'Portal'
                ]
                if any(re.search(p, text, re.IGNORECASE) for p in BLACKLIST_PATTERNS):
                    continue

                if is_noise and not has_spots: continue
                if len(text) < 10 and not has_spots: continue

                # --- EXTRACTION ---
                # Split cleaning
                if "," in text:
                    parts = text.split(",")
                    if len(parts) > 1 and (re.search(r'\d', parts[1]) or "locuri" in parts[1].lower()):
                         text = parts[0].strip()
                
                if ";" in text: text = text.split(";")[0].strip()
                
                program_name = text
                spots_budget, spots_tax = None, None
                
                m_both = RE_SPOTS.search(raw_text) # Search raw text for numbers to handle newlines
                if m_both:
                    spots_budget = int(m_both.group(1))
                    spots_tax = int(m_both.group(2))
                else:
                    m_bud = RE_BUDGET.search(raw_text)
                    m_tax = RE_TAX.search(raw_text)
                    if m_bud: spots_budget = int(m_bud.group(1))
                    if m_tax: spots_tax = int(m_tax.group(1))

                # Language
                language = "Romanian"
                if "englez" in text.lower() or "english" in text.lower(): language = "English"
                elif "francez" in text.lower(): language = "French"

                # Create Entity
                program_uid = ProvenanceMixin.generate_uid(f"{url}|{ProvenanceMixin.normalize_name(program_name)}")
                level = "Licenta" if "licenta" in url else "Master"
                
                confidence = 0.5
                source_type = "html_list_mixed"
                if spots_budget: 
                    confidence += 0.3
                    source_type = "html_text_parsed"

                # Faculty UID resolution (needed for Program model)
                # Ideally Adapter doesn't know about Hash generation logic if it's external,
                # but ProvenanceMixin is available.
                faculty_uid_hash = ProvenanceMixin.generate_uid(f"faculty:{faculty_slug}")

                p = Program(
                    uid=program_uid,
                    run_id="adapter_run", # Placeholder, will be overwritten by Scraper
                    source_url=url,
                    content_hash=ProvenanceMixin.generate_content_hash(text),
                    name=program_name,
                    faculty_uid=faculty_uid_hash,
                    faculty_slug=faculty_slug,
                    level=level,
                    duration_years="4 ani" if level == "Licenta" else "2 ani",
                    language=language,
                    spots_raw=text if has_spots else None,
                    spots_budget=spots_budget,
                    spots_tax=spots_tax,
                    source_type=source_type,
                    accuracy_confidence=confidence
                )
                
                if current_domain: 
                    p.spots_raw = f"{p.spots_raw or text} [Domain: {current_domain}]"

                programs.append(p)
                
        return programs

    def extract_grade_candidates(self, html: str, url: str) -> List[Dict[str, Any]]:
        """
        Scans for "Rezultate Admitere" PDFs.
        """
        candidates = []
        soup = BeautifulSoup(html, "html.parser")
        container = soup.find("div", id="continut_standard") or soup.find("div", id="main_content") or soup
        
        KEYWORDS = ["rezultate", "admis", "liste", "clasament", "medii"]
        NEGATIVE_KEYWORDS = ["cazare", "burse", "programare"]
        
        for link in container.find_all("a", href=True):
            href = link["href"].strip()
            text = link.get_text(separator=" ", strip=True).lower()
            
            if href.lower().endswith(".pdf"):
                # Score relevance
                score = 0
                if any(k in text for k in KEYWORDS): score += 10
                if any(k in text for k in NEGATIVE_KEYWORDS): score -= 100
                if "2026" in text or "2026" in href: score += 5 
                # (Ideally use dynamic year logic but simple check is OK for now)
                
                if score > 0:
                    full_url = urljoin(url, href)
                    candidates.append({
                        "pdf_url": full_url,
                        "link_text": link.get_text(strip=True),
                        "source_url": url,
                        "score": score,
                        "discovered_at": datetime.datetime.now().isoformat()
                    })
        
        # Sort by score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    def parse_grades(self, pdf_path: str) -> Dict[str, float]:
        """
        Delegates to the Privacy-Safe Grade Parser.
        """
        return self.grade_parser.extract_min_grades(pdf_path)
