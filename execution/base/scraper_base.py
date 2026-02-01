from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime, timezone
import hashlib

from execution.base.http_client import PoliteHTTPClient
from execution.base.browser_manager import BrowserManager
from execution.models.provenance import ProvenanceMixin
from pydantic import BaseModel
from execution.scrapers.adapter_interface import UniversityAdapter
from rapidfuzz import process, fuzz

class BaseScraper(ABC):
    """
    Abstract Base Scraper enforcing the Bronze-Silver-Gold lifecycle.
    Now Adapter-Driven (Phase 8.5).
    """
    def __init__(self, run_id: str, adapter: UniversityAdapter):
        self.run_id = run_id
        self.adapter = adapter
        self.university_code = adapter.get_university_slug()
        self.logger = logging.getLogger(f"scraper.{self.university_code}")
        
        # Infrastructure
        self.http_client = PoliteHTTPClient()
        self.browser_manager = BrowserManager()
        
        # Paths
        self.base_dir = Path(f"data/runs/{run_id}")
        self.raw_dir = self.base_dir / "raw"
        self.errors_dir = self.base_dir / "errors"
        self.snapshots_dir = self.base_dir / "snapshots"

    def setup_directories(self, faculty_slug: str):
        """Ensure specific raw/error directories exist for this faculty."""
        (self.raw_dir / faculty_slug / "programs").mkdir(parents=True, exist_ok=True)
        (self.raw_dir / faculty_slug / "pdfs").mkdir(parents=True, exist_ok=True)
        (self.errors_dir / faculty_slug).mkdir(parents=True, exist_ok=True)

    def save_snapshot(self, html: str, url: str, faculty_slug: str) -> str:
        """
        Bronze Layer: Save immutable HTML snapshot.
        Returns: SHA256 content hash.
        """
        content_hash = ProvenanceMixin.generate_content_hash(html)
        uid = ProvenanceMixin.generate_uid(url) # UID of the PAGE (canonical URL already passed in)
        
        # Filename: timestamp_urlhash_snapshot.html
        # Fix V3.2: Use URL hash in filename to distinguish multiple pages for same faculty
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{timestamp}_{uid[:8]}_snapshot.html"
        path = self.raw_dir / faculty_slug / filename
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
            
        return content_hash

    def save_entity(self, entity_model: BaseModel, faculty_slug: str):
        """
        Silver Layer: Save validated Pydantic entity to JSON.
        """
        if entity_model.entity_type == "faculty":
            path = self.raw_dir / faculty_slug / f"{entity_model.uid}.json"
        else:
            path = self.raw_dir / faculty_slug / "programs" / f"{entity_model.uid}.json"
            
        with open(path, "w", encoding="utf-8") as f:
            f.write(entity_model.model_dump_json(indent=2))

    def quarantine_error(self, faculty_slug: str, url: str, error: Exception, raw_data: Optional[Dict] = None):
        """
        Quarantine Layer: Save error details.
        """
        timestamp = datetime.now().isoformat()
        err_data = {
            "timestamp": timestamp,
            "url": url,
            "error": str(error),
            "raw_capture": str(raw_data) if raw_data else None
        }
        
        filename = f"error_{int(datetime.now().timestamp())}.json"
        path = self.errors_dir / faculty_slug / filename
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(err_data, f, indent=4, default=str, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to quarantine error: {e}")

    def run(self):
        """
        Main execution loop (Adapter Driven).
        """
        self.logger.info(f"Starting Scraper for {self.adapter.get_university_name()}...")
        
        faculties = self.adapter.discover_faculties()
        manifest = {
            "run_id": self.run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "faculties_total": len(faculties),
            "successful": []
        }
        
        current_idx = 0
        for fac_config in faculties:
            slug = fac_config["slug"]
            name = fac_config["name"]
            urls = fac_config.get("urls", [])
            if not urls and "url" in fac_config: urls = [fac_config["url"]]
            
            current_idx += 1
            self.logger.info(f"[{current_idx}/{len(faculties)}] Processing: {name} ({slug})")
            
            self.setup_directories(slug)
            
            pdf_queue = []
            
            for url in urls:
                if not url: continue
                try:
                    # 1. Bronze: Fetch & Snapshot
                    c_url = ProvenanceMixin.canonicalize_url(url)
                    resp = self.http_client.get(c_url)
                    
                    # Encoding fix (Romanian standard)
                    if resp.encoding == 'ISO-8859-1' and 'text/html' in resp.headers.get('Content-Type', ''):
                        resp.encoding = 'utf-8'
                    if "Ä" in resp.text and "ă" not in resp.text:
                        resp.encoding = 'utf-8'
                        
                    html = resp.text
                    self.save_snapshot(html, c_url, slug)
                    
                    # 2. Silver: Extraction via Adapter
                    self._extract_from_snapshot(html, c_url, slug, name, pdf_queue)
                    
                except Exception as e:
                    self.logger.error(f"Failed to scrape {slug} - {url}: {e}")
                    self.quarantine_error(slug, url, e)

            # Save PDF Queue
            if pdf_queue:
                queue_path = self.raw_dir / slug / "pdf_queue.json"
                with open(queue_path, "w", encoding="utf-8") as f:
                    json.dump(pdf_queue, f, indent=2, ensure_ascii=False)
            
            manifest["successful"].append(slug)

        # Finalize
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.base_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def _enrich_from_pdf(self, slug: str, pdf_path: str, pdf_url: str):
        """
        Stage B: Parse PDF and update Program entities.
        """
        try:
            spots_data = self.adapter.parse_spots(pdf_path)
            if not spots_data: return

            self.logger.info(f"Enriching {slug} with {len(spots_data)} rows from PDF.")

            # Load all programs for this faculty
            programs_dir = self.raw_dir / slug / "programs"
            programs = []
            program_files = {} # idx -> filepath

            if not programs_dir.exists(): return

            # Read all JSONs
            for i, p_file in enumerate(programs_dir.glob("*.json")):
                try:
                    with open(p_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        programs.append(data)
                        program_files[i] = p_file
                except: pass

            if not programs: return

            # Match
            program_names = [p["name"] for p in programs]

            for row in spots_data:
                p_name = row["program_name"]
                # Fuzzy match
                match = process.extractOne(p_name, program_names, scorer=fuzz.token_sort_ratio)
                if match:
                    best_name, score, idx = match
                    if score > 85:
                        # Update
                        prog = programs[idx]
                        prog["spots_budget"] = row["spots_budget"]
                        prog["spots_tax"] = row["spots_tax"]
                        prog["spots_raw"] = f"PDF: {row['raw_row']} (Score: {score:.1f})"

                        # Save immediately
                        with open(program_files[idx], "w", encoding="utf-8") as f:
                            json.dump(prog, f, indent=2, ensure_ascii=False)

                        self.logger.info(f"Matched '{p_name}' -> '{best_name}' (B:{row['spots_budget']} T:{row['spots_tax']})")
        except Exception as e:
            self.logger.error(f"Enrichment failed for {pdf_path}: {e}")

    def _extract_from_snapshot(self, html: str, url: str, slug: str, faculty_name: str, pdf_queue: List[Dict]):
        """
        Delegates extraction logic to the Adapter.
        """
        # 1. Create Faculty Entity
        faculty_uid = ProvenanceMixin.generate_uid(f"faculty:{slug}")
        from execution.models.faculty import Faculty # Lazy import to avoid circular dep
        
        faculty = Faculty(
            uid=faculty_uid,
            run_id=self.run_id,
            source_url=url,
            content_hash=ProvenanceMixin.generate_content_hash(html),
            name=faculty_name,
            slug=slug
        )
        self.save_entity(faculty, slug)
        
        # 2. Extract PDF Candidates (Adapter)
        new_pdfs = self.adapter.extract_pdf_candidates(html, url)
        # Dedupe and add to queue
        existing_urls = {p["pdf_url"] for p in pdf_queue}
        for pdf in new_pdfs:
             if pdf["pdf_url"] not in existing_urls:
                 pdf["faculty_slug"] = slug
                 pdf["status"] = "queued"
                 pdf_queue.append(pdf)
                 existing_urls.add(pdf["pdf_url"])
                 
        # 2b. Extract Grade Candidates (New Phase 8.6)
        grade_pdfs = self.adapter.extract_grade_candidates(html, url)
        if grade_pdfs:
             self.logger.info(f"[{slug}] Found {len(grade_pdfs)} potential 'Results' PDFs.")
             all_grades = {}
             
             # Create grades dir
             (self.raw_dir / slug / "grades").mkdir(parents=True, exist_ok=True)
             
             for g_pdf in grade_pdfs:
                 # Download if score is high enough?
                 # For now, simplistic approach: Download Top 1
                 pdf_url = g_pdf["pdf_url"]
                 try:
                      pdf_resp = self.http_client.get(pdf_url)
                      pdf_filename = f"results_{hashlib.md5(pdf_url.encode()).hexdigest()[:8]}.pdf"
                      pdf_path = self.raw_dir / slug / "pdfs" / pdf_filename
                      
                      with open(pdf_path, "wb") as f:
                          f.write(pdf_resp.content)
                          
                      # Parse
                      grades_map = self.adapter.parse_grades(str(pdf_path))
                      if grades_map:
                          all_grades.update(grades_map)
                          self.logger.info(f"[{slug}] Extracted {len(grades_map)} grades from {g_pdf['link_text']}")
                 except Exception as e:
                     self.logger.warning(f"Failed to process grade PDF {pdf_url}: {e}")
            
             # Save Grade Map
             if all_grades:
                 g_path = self.raw_dir / slug / "grades" / f"grades_map_{int(datetime.now().timestamp())}.json"
                 with open(g_path, "w", encoding="utf-8") as f:
                     json.dump(all_grades, f, indent=2)
        
        # 3. Extract Programs (Adapter)
        programs = self.adapter.extract_programs_from_html(html, url, slug)
        for prog in programs:
            prog.run_id = self.run_id # Ensure run_id is propagated
            self.save_entity(prog, slug)
        
        if programs:
            self.logger.info(f"[{slug}] Extracted {len(programs)} programs from HTML.")
        else:
            self.logger.info(f"[{slug}] No HTML programs found (PDF-only or empty).")

        # 4. Process PDF Queue (Stage A) - Download Top Candidates
        if pdf_queue:
            ranker = self.adapter.get_pdf_ranker()
            # Rank
            ranked = ranker.rank_candidates(pdf_queue, target_type="SPOTS")
            
            # Download Top 3
            top_candidates = ranked[:3]
            for cand in top_candidates:
                pdf_url = cand["pdf_url"]
                pdf_filename = f"spots_{hashlib.md5(pdf_url.encode()).hexdigest()[:8]}.pdf"
                pdf_path = self.raw_dir / slug / "pdfs" / pdf_filename
                
                # Check cache
                if not pdf_path.exists():
                    try:
                        self.logger.info(f"Downloading candidate PDF: {cand['link_text']}")
                        resp = self.http_client.get(pdf_url)
                        (self.raw_dir / slug / "pdfs").mkdir(parents=True, exist_ok=True)
                        with open(pdf_path, "wb") as f:
                            f.write(resp.content)
                    except Exception as e:
                        self.logger.error(f"Failed to download {pdf_url}: {e}")
                        continue
                
                # Update Candidate with local path for Matcher
                cand["local_path"] = str(pdf_path.resolve())
            
            # Save Queue (Matcher reads this)
            q_path = self.raw_dir / slug / "pdf_queue.json"
            with open(q_path, "w", encoding="utf-8") as f:
                json.dump(pdf_queue, f, indent=2)

            # 5. Process PDF Queue (Stage B) - Enrichment
            self.logger.info(f"[{slug}] Starting Stage B: PDF Enrichment...")
            for cand in top_candidates:
                if "local_path" in cand:
                    self._enrich_from_pdf(slug, cand["local_path"], cand["pdf_url"])
