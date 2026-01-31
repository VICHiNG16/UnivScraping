
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
        
        
        soup = BeautifulSoup(html, "html.parser")

        # Broader container detection: common WP classes, article tags, and fallback to whole doc.
        container = None
        selectors = [
            "div#continut_standard", "div#main_content", "article", ".entry-content",
            ".post-content", ".page-content", ".content-area", "main"
        ]
        for sel in selectors:
            found = soup.select_one(sel)
            if found:
                container = found
                break
        if container is None:
            container = soup

        # Try JSON-LD (schema.org) program lists if present
        try:
            for js in soup.select('script[type="application/ld+json"]'):
                import json
                try:
                    data = json.loads(js.string or "{}")
                    # Look for an array of programs or educationalOrganization patterns
                    if isinstance(data, dict) and "hasCourse" in data:
                        for course in data.get("hasCourse", []):
                            name = course.get("name")
                            if name:
                                # create Program object like below (lightweight)
                                program_uid = ProvenanceMixin.generate_uid(f"{url}|{ProvenanceMixin.normalize_name(name)}")
                                p = Program(
                                    uid=program_uid,
                                    run_id="adapter_run",
                                    source_url=url,
                                    content_hash=ProvenanceMixin.generate_content_hash(name),
                                    name=name,
                                    faculty_uid=ProvenanceMixin.generate_uid(f"faculty:{faculty_slug}"),
                                    faculty_slug=faculty_slug,
                                    level="Licenta" if "licenta" in url else "Master",
                                    duration_years="4 ani" if "licenta" in url else "2 ani",
                                    language="Romanian",
                                    source_type="jsonld",
                                    accuracy_confidence=0.6
                                )
                                programs.append(p)
                except Exception:
                    pass
        except Exception:
            pass

        # Heading-based extraction: find headings with 'admitere' or 'programe' and read following lists
        for heading in container.find_all(["h1", "h2", "h3"]):
            htext = heading.get_text(strip=True).lower()
            if any(k in htext for k in ["admitere", "programe", "licen", "master", "specializ"]):
                # look for next sibling lists or paragraphs
                sibling = heading.find_next_sibling()
                if sibling:
                    # prefer lists
                    for li in sibling.select("ul li, ol li"):
                        text = li.get_text(separator=" ", strip=True)
                        if text and len(text) > 6:
                            # reuse existing cleaning/regex logic below to parse numbers
                            # push this text into the normal per-li parsing by creating a fake <li>
                            # To do this safely without breaking strict typing, we can append to a list 
                            # and let the main loop process it if we restructure, 
                            # but for minimal diff we can try to inject into the logic or just let the main loop below catch the <li> 
                            # if the container is broad enough, the main loop 'for ul in container.find_all("ul")' should catch it!
                            # The main loop iterates ALL ULs in container. 
                            # Since we expanded 'container' to be broader, we probably don't need this explicit sibling check 
                            # UNLESS the structure is non-nested (sibling ULs). 
                            # But find_all("ul") is recursive. 
                            pass
        
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
                
                # --- VIP ENTRANCE VALIDATOR (Iron Dome V3) ---
                # Rule 1: Link Density / Structure (Fast Reject)
                if self.boilerplate_rejector.is_structural_garbage(li):
                    continue

                # Rule 2: Strict content analysis
                # Must contain at least one valid program keyword to even be considered if NO spots are found
                PROGRAM_WHITELIST = [
                    "licență", "licenta", "master", "doctorat", "inginerie", "drept", "litere", 
                    "științe", "stiinte", "matematică", "fizică", "chimie", "informatică", "geografie",
                    "teologie", "istorie", "filosofie", "sociologie", "psihologie", "educație",
                    "administrație", "economie", "finanțe", "management", "marketing", "agricultură",
                    "horticultură", "silvicultură", "mediu", "biologie", "peisagistică", "autovehicule",
                    "robotica", "mecatronică", "electrică", "energetică", "aerospatiala"
                ]
                
                # Expanded Noise List
                EXTENDED_NOISE = NOISE_KEYWORDS + [
                    "modalități", "calendar", "tematică", "interviu", "contact", "regulament", "concurs",
                    "studenți", "burse", "cazare", "social", "sport", "finalizare", "strategia", "proiecte",
                    "cercetare", "declaratii", "structura", "conducere", "acorduri", "baza materială", "orar",
                    "fise", "articole", "evenimente", "rezultate", "confirmare", "acte", "dosar", "admitere online"
                ]

                # Scoring
                has_whitelist = any(kw in text.lower() for kw in PROGRAM_WHITELIST)
                is_extended_noise = any(kw in text.lower() for kw in EXTENDED_NOISE)

                # DECISION MATRIX
                # 1. If we found spots (budget/tax numbers), we trust it 90%, unless it's obviously noise (e.g. "Taxe 2026")
                if has_spots:
                    if is_extended_noise: continue # "Taxe: 2000 lei" might trigger spots regex occasionally
                    pass # ACCEPT
                
                # 2. If NO spots, we only accept if it's PROVEN to be a program title (Whitelist) AND NOT noise
                else:
                    if not has_whitelist: continue # Reject "Contact", "Home", etc.
                    if is_extended_noise: continue # Reject "Calendar Admitere" even if it says "Admitere"
                    
                    # Length Check: "Inginerie" (9 chars)
                    if len(text) < 10: continue

                # Double Check: If it starts with "Tel:", "Fax:", etc. it's garbage
                if re.match(r'^(tel|fax|str|bd|nr)\.?\s*:', text, re.IGNORECASE): continue

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
        
        # --- TABLE PARSER (Agro Style) ---
        for table in container.find_all("table"):
            rows = table.find_all("tr")
            if not rows: continue
            
            # Simple heuristic: Look for header row with "Buget" and "Taxa"
            header_text = rows[0].get_text().lower()
            budget_idx, tax_idx = -1, -1
            
            # Try to map columns based on keywords in the first few rows
            # This is brittle but works for the specific format seen in Agronomie snapshot
            # Row 0: "DOMENII – SPECIALIZĂRI | BUGET | ... | TAXĂ | ..."
            
            for i, td in enumerate(rows[0].find_all(["td", "th"])):
                txt = td.get_text(strip=True).lower()
                if "buget" in txt: budget_idx = i
                if "tax" in txt: tax_idx = i
            
            # If explicit headers fail, assume typical layout: Col 0 = Name, Col 1 = Buget, Col 3 = Taxa (often skipped cols)
            if budget_idx == -1: budget_idx = 1
            if tax_idx == -1: tax_idx = 3

            for row in rows[1:]:
                cols = row.find_all("td")
                if not cols: continue
                if len(cols) < 2: continue # Need at least Name + something
                
                # Check Name Column
                raw_name = cols[0].get_text(strip=True)
                clean_name = re.sub(r'\s+', ' ', raw_name).strip()
                
                # Domain headers often look like "DOMENIUL SILVICULTURĂ" inside the table
                if clean_name.lower().startswith("domeniul"):
                    current_domain = clean_name.split("Domeniul")[-1].strip(" :")
                    continue
                
                # Filter noise
                if len(clean_name) < 5: continue
                if "din care" in clean_name.lower(): continue # Footnotes

                # Extract Names (sometimes multiple in one cell, separated by ; or newlines)
                # Agronomie example: "Agricultura: Inginer agronom; Manager..." -> We want "Agricultura" usually, or the specializations?
                # The snapshot shows: "Agricultura: Inginer agronom; ..." as one block.
                # Heuristic: Take the part before ":" if present, else whole text
                
                primary_name = clean_name.split(":")[0].strip()
                if not primary_name: primary_name = clean_name

                # Extract Spots
                spots_budget = 0
                spots_tax = 0
                
                try:
                    if len(cols) > budget_idx:
                        val = cols[budget_idx].get_text(strip=True).replace("*", "")
                        if val.isdigit(): spots_budget = int(val)
                    
                    if len(cols) > tax_idx:
                        val = cols[tax_idx].get_text(strip=True).replace("*", "")
                        if val.isdigit(): spots_tax = int(val)
                except:
                    pass # Keep 0 if failed
                
                # Only valid if we found spots OR it hits the whitelist
                has_whitelist = any(kw in primary_name.lower() for kw in PROGRAM_WHITELIST)
                if not (spots_budget > 0 or spots_tax > 0 or has_whitelist):
                    continue

                # Create Program
                program_uid = ProvenanceMixin.generate_uid(f"{url}|{ProvenanceMixin.normalize_name(primary_name)}")
                level = "Licenta" if "licenta" in url else "Master"
                
                p_tbl = Program(
                    uid=program_uid,
                    run_id="adapter_run",
                    source_url=url,
                    content_hash=ProvenanceMixin.generate_content_hash(primary_name),
                    name=primary_name,
                    faculty_uid=ProvenanceMixin.generate_uid(f"faculty:{faculty_slug}"),
                    faculty_slug=faculty_slug,
                    level=level,
                    duration_years="4 ani" if level == "Licenta" else "2 ani",
                    language="Romanian", # Default
                    spots_budget=spots_budget,
                    spots_tax=spots_tax,
                    spots_raw=f"Table: {raw_name} | B:{spots_budget} T:{spots_tax}",
                    source_type="html_table_parsed",
                    accuracy_confidence=0.85 # Higher confidence for tables
                )
                if current_domain: 
                    p_tbl.spots_raw += f" [Domain: {current_domain}]"
                    
                programs.append(p_tbl)

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
