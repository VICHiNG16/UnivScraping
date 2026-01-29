import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import re
from rapidfuzz import fuzz
import datetime
from execution.scrapers.ucv.pdf_parser import PDFParser

logger = logging.getLogger("matcher")

class RomanianProgramMatcher:
    """
    V4 Matching Engine for Romanian Academic Programs
    Uses multi-signal fusion: Name + Level + Domain + Code
    """
    def __init__(self, html_programs: List[Dict], pdf_rows: List[Dict]):
        self.html_programs = html_programs
        self.pdf_rows = pdf_rows
        # Pre-compile regex for performance
        self.abbrevs = {
            r'\bcalc\b': 'calculatoare',
            r'\beng\b': 'engleza',
            r'\bing\b': 'inginerie',
            r'\bauto\b': 'automatica',
            r'\binf\b': 'informatica',
            r'\bmas\b': 'master',
            r'\blic\b': 'licenta'
        }

    def match_all(self) -> List[Dict]:
        """
        Returns a list of match results for each HTML program.
        """
        results = []
        for prog in self.html_programs:
            match_result = self._find_best_match(prog)
            results.append(match_result)
        return results

    def _find_best_match(self, html_prog: Dict) -> Dict:
        """
        Finds the best PDF row for a single HTML program.
        """
        best_row = None
        best_score = 0.0
        
        # Pre-normalize HTML name
        html_norm = self._romanian_normalize(html_prog.get("name", ""))
        html_norm = self._expand_abbreviations(html_norm)

        candidates = []
        
        for row in self.pdf_rows:
            score = self._calculate_match_score(html_prog, row, html_norm_precomputed=html_norm)
            
            if score > 0.01:
                candidates.append((score, row))
        
        # Sort by score desc
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        if not candidates:
             return {"program": html_prog, "match": None, "score": 0.0, "status": "no_match"}

        best_score, best_row = candidates[0]
        
        # Ambiguity check
        status = "match"
        if len(candidates) > 1:
            second_score = candidates[1][0]
            if (best_score - second_score) < 0.15:
                status = "ambiguous" # Close call
        
        if best_score < 0.5:
            status = "low_confidence"

        return {
            "program": html_prog,
            "match": best_row,
            "score": best_score,
            "status": status
        }

    def _calculate_match_score(self, html_prog: Dict, pdf_row: Dict, html_norm_precomputed: str = None) -> float:
        """
        Multi-signal scoring.
        """
        # 0. Level Check (Critical Hard Filter - V4 Refinement)
        html_level = (html_prog.get("level") or "").lower()
        pdf_level = (pdf_row.get("level") or "").lower() # PDF parser might not always set this
        
        # Normalize levels for comparison
        is_html_lic = "licenta" in html_level or "licență" in html_level
        is_html_mas = "master" in html_level
        
        # If PDF data implies level (often from header context), strictly enforce it.
        # Assuming PDF parser provides 'level' context now.
        if pdf_level:
            is_pdf_lic = "licenta" in pdf_level or "licență" in pdf_level
            is_pdf_mas = "master" in pdf_level
            
            if (is_html_lic and is_pdf_mas) or (is_html_mas and is_pdf_lic):
                return 0.0

        # ... (rest of scoring)
        
        # 1. Name Similarity (40%)
        if not html_norm_precomputed:
            html_norm = self._romanian_normalize(html_prog.get("name", ""))
            html_norm = self._expand_abbreviations(html_norm)
        else:
            html_norm = html_norm_precomputed
            
        pdf_norm = self._romanian_normalize(pdf_row.get("program_name", ""))
        pdf_norm = self._expand_abbreviations(pdf_norm)
        
        # Hybrid fuzzy score
        token_set = fuzz.token_set_ratio(html_norm, pdf_norm) / 100.0
        partial = fuzz.partial_ratio(html_norm, pdf_norm) / 100.0
        
        name_score = max(token_set, partial)
        
        # 2. Level Signal (30%) - If names match, level confirmation boosts it
        level_score = 0.0
        if html_level and pdf_level:
             # loose match
             if html_level in pdf_level or pdf_level in html_level:
                 level_score = 1.0
        elif not html_level and not pdf_level:
            level_score = 0.5 # Neutral
        
        # 3. Domain Context (20%) - From V3.6 metdata
        domain_score = 0.0
        html_domain = (html_prog.get("domain") or "").lower()
        pdf_domain = (pdf_row.get("domain") or "").lower()
        
        if html_domain and pdf_domain:
            if fuzz.partial_ratio(html_domain, pdf_domain) > 80:
                domain_score = 1.0
        
        # Weighted Sum
        # If name is totally off, other signals don't matter matching garbage
        if name_score < 0.3:
            return 0.0
            
        final_score = (name_score * 0.5) + (level_score * 0.3) + (domain_score * 0.2)
        
        # Bonus for exact abbrev matches "Calc." == "Calculatoare" (handled by expansion + token_set)
        
        return min(final_score, 1.0)

    def _romanian_normalize(self, text: str) -> str:
        if not text: return ""
        text = text.lower()
        # Diacritics Mapping (Strip to ASCII for robust fuzzy matching)
        # We map all variants to their base ASCII char
        text = text.replace("ş", "s").replace("ș", "s").replace("ţ", "t").replace("ț", "t")
        text = text.replace("ă", "a").replace("â", "a").replace("î", "i")
        
        # Remove parens content often containing "textul" or "limba" if trivial, 
        # but keep "engleza"
        # For now, just remove special chars
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split())

    def _expand_abbreviations(self, text: str) -> List[str]:
        for pattern, replacement in self.abbrevs.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    def _resolve_faculty_uid(self, slug: str) -> Optional[str]:
        """
        Locates the Faculty entity JSON in the Raw directory to get its hash UID.
        """
        raw_dir = self.base_dir / "raw" / slug
        if not raw_dir.exists(): return None
        
        # Look for the only JSON file that IS NOT pdf_queue.json
        for f in raw_dir.glob("*.json"):
            if f.name == "pdf_queue.json": continue
            if f.name == "manifest.json": continue
            
            try:
                with open(f, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    if data.get("entity_type") == "faculty":
                        return data.get("uid")
            except Exception:
                continue
        return None

from execution.enrichment.pdf_ranker import PDFTruthRanker

class DataFusionEngine:
    """
    Fuses scraped HTML data (Programs) with parsed PDF data (Spots).
    """
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.base_dir = Path("data/runs") / run_id
        self.pdf_parser = PDFParser()
        # V9: Validator
        from execution.processors.validator import SemanticValidator
        self.validator = SemanticValidator()
        
        # V8: Dynamic Year
        self.pdf_parser = PDFParser()
        # V8: Dynamic Year
        self.admission_year = datetime.datetime.now().year
        self.ranker = PDFTruthRanker(admission_year=self.admission_year)

    def _resolve_faculty_uid(self, slug: str) -> Optional[str]:
        """
        Locates the Faculty entity JSON in the Raw directory to get its hash UID.
        """
        raw_dir = self.base_dir / "raw" / slug
        if not raw_dir.exists(): return None
        
        # Look for the only JSON file that IS NOT pdf_queue.json
        for f in raw_dir.glob("*.json"):
            if f.name == "pdf_queue.json": continue
            if f.name == "manifest.json": continue
            
            try:
                with open(f, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    if data.get("entity_type") == "faculty":
                        return data.get("uid")
            except Exception:
                continue
        return None
    
    def enrich_run(self):
        """
        Main entry point: Enriches the entire run.
        """
        # Load Manifest or Fallback
        manifest_path = self.base_dir / "manifest.json"
        
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            successful_faculties = manifest.get("successful", [])
        else:
            logger.warning("Manifest not found. Scanning 'raw' directory for faculties...")
            raw_dir = self.base_dir / "raw"
            if raw_dir.exists():
                successful_faculties = [d.name for d in raw_dir.iterdir() if d.is_dir()]
            else:
                successful_faculties = []
        
        # Iterate Faculties
        for slug in successful_faculties:
            self._enrich_faculty(slug)
    
    def _enrich_faculty(self, slug: str):
        logger.info(f"[{slug}] Starting enrichment...")
        
        # 0. Resolve Faculty UID
        faculty_uid = self._resolve_faculty_uid(slug)
        if not faculty_uid:
            logger.warning(f"[{slug}] Could not resolve Faculty UID. Using slug as fallback.")
            faculty_uid = slug

        # 1. Load Scraped Programs
        programs_dir = self.base_dir / "raw" / slug / "programs"
        if not programs_dir.exists():
            logger.warning(f"[{slug}] No programs dir.")
            return
            
        programs = []
        for p_file in programs_dir.glob("*.json"):
            with open(p_file, "r", encoding="utf-8") as f:
                programs.append(json.load(f))
        
        if not programs:
            logger.warning(f"[{slug}] No programs found. Attempting PDF-Only Synthesis...")
            # Do NOT return. Proceed to find PDF.

        # 2. Find and Parse "Spots PDF"
        pdf_queue_path = self.base_dir / "raw" / slug / "pdf_queue.json"
        if not pdf_queue_path.exists():
            logger.info(f"[{slug}] No pdf_queue.")
            return
            
        with open(pdf_queue_path, "r", encoding="utf-8") as f:
            queue = json.load(f)
        
        spots_candidates = self._identify_spots_pdf(queue)
        if not spots_candidates:
            logger.warning(f"[{slug}] Could not identify ANY relevant PDF.")
            return
            
        pdf_rows_list = [] # V8.7: List of {rows, url, score}
        
        for candidate in spots_candidates:
            pdf_path = Path(candidate["local_path"])
            if not pdf_path.exists():
                 logger.error(f"[{slug}] PDF missing: {pdf_path}")
                 continue

            logger.info(f"[{slug}] Attempting extraction from: {candidate['link_text']} (Score: Best)")
            
            # V8: Stage B - Content Evaluation
            metrics = self.ranker.evaluate_content(str(pdf_path))
            c_score = metrics.get("content_score", 0)
            logger.info(f"[{slug}] Candidate Content Analysis: Score={c_score} | Density={metrics.get('text_density'):.1f}% | Rows={metrics.get('rows_with_numbers')}")
            
            if c_score < -5:
                # Likely scanned image or totally irrelevant
                logger.warning(f"[{slug}] Skipping {candidate['link_text']} due to poor content quality (Score: {c_score}).")
                continue

            try:
                raw_rows = self.pdf_parser.extract_spots(str(pdf_path))
                if raw_rows:
                    # V7: Post-Extraction Validation
                    valid_rows = [r for r in raw_rows if len(r['program_name']) > 5 and "copie" not in r['program_name'].lower()]
                    
                    if not valid_rows or len(valid_rows) < len(raw_rows) * 0.5:
                         logger.warning(f"[{slug}] PDF yielded mostly garbage rows (e.g. '{raw_rows[0].get('program_name')}'). Discarding.")
                         continue # Try next candidate
                    
                    pdf_rows_list.append({
                        "rows": valid_rows,
                        "url": candidate["pdf_url"],
                        "score": c_score,
                        "link_text": candidate["link_text"]
                    })
                    logger.info(f"[{slug}] Success! Extracted {len(valid_rows)} rows from {candidate['link_text']}")
                    # V8.7: Do NOT break. Continue to next candidate.
                    # break 
                else:
                     logger.warning(f"[{slug}] Extraction failed (0 rows) for {pdf_path.name}. Trying next candidate...")
            except Exception as e:
                logger.error(f"Error parsing {pdf_path}: {e}")

        if not pdf_rows_list:
            logger.warning(f"[{slug}] All PDF candidates failed to yield Data.")
            return

        # 4. Phase 8.6: Load and Fuse Grades
        grades_map = self._load_grades(slug)
        
        # 3. Match and Update (Phase 8.7: Multi-PDF)
        # Iterate ALL valid candidates and fuse
        for res in pdf_rows_list:
             self._fuse_data(slug, programs, res["rows"], res["url"], faculty_uid, grades_map, res["score"], res["link_text"])
        
    def _load_grades(self, slug: str) -> Dict[str, float]:
        """
        Loads the most recent grades_map JSON from raw/slug/grades.
        """
        grades_dir = self.base_dir / "raw" / slug / "grades"
        if not grades_dir.exists(): return {}
        
        # Find latest file
        files = list(grades_dir.glob("grades_map_*.json"))
        if not files: return {}
        
        latest = max(files, key=lambda f: f.stat().st_mtime)
        try:
            with open(latest, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _identify_spots_pdf(self, pdf_queue: List[Dict]) -> List[Dict]:
        """
        Identifies the best PDF candidates for "Unknown Spots" using the PDFTruthRanker.
        V8: Evidence-Driven Ranking (Replaces V5.1 Heuristics)
        """
        from execution.enrichment.pdf_ranker import PDFTruthRanker
        
        # Filter: Only valid links
        candidates = [p for p in pdf_queue if p.get("link_text") and (p.get("pdf_url") or p.get("url"))]
        
        # Ranker
        ranker = PDFTruthRanker(admission_year=2026) # TODO: Make Configurable
        ranked_candidates = ranker.rank_candidates(candidates)
        
        # Log top picks
        if ranked_candidates:
            top = ranked_candidates[0]
            logger.info(f"Top PDF Candidate: '{top.get('link_text')}' (Score: {top.get('stage_a_score')})")
            
        return ranked_candidates

    def _fuse_data(self, slug: str, programs: List[Dict], pdf_rows: List[Dict], pdf_url: str, faculty_uid: str, grades_map: Dict = None, likelihood_score: float = 0, source_name: str = ""):
        """
        Fuzzy matching logic using V4 Matcher.
        V8: Now accepting explicit faculty_uid (Hash) and slug.
        """
        # V9: Zero Garbage Validation (apply to all PDF rows)
        filtered_rows = []
        for row in pdf_rows:
            val_res = self.validator.validate_program_name(row.get("program_name", ""))
            if val_res["status"] == "FAIL":
                logger.warning(f"[{slug}] Dropping Garbage Candidate: '{row.get('program_name')}' (Reason: {val_res['reason']})")
                continue
            if val_res["status"] == "QUARANTINE":
                logger.warning(f"[{slug}] Quarantining Candidate: '{row.get('program_name')}' (Score: {val_res['score']})")
                self._save_quarantine(slug, row, val_res)
                continue
            filtered_rows.append(row)

        if not filtered_rows:
            logger.warning(f"[{slug}] All PDF rows failed validation for source '{source_name}'.")
            return

        # V6: PDF-First Synthesis
        if not programs and filtered_rows:
            logger.info(f"[{slug}] PDF-Only Mode: Synthesizing {len(filtered_rows)} programs from PDF.")
            for row in filtered_rows:
                # Create Minimal Program Entity
                match_id = hashlib.sha256(f"{slug}|{row['program_name']}".encode()).hexdigest()
                career_paths = self._infer_career_paths(row['program_name'])
                prog = {
                    "uid": match_id,
                    "name": row['program_name'],
                    "spots_budget": row['spots_budget'],
                    "spots_tax": row['spots_tax'],
                    "language": "ro", # Default
                    "level": row.get("level", "Master"), # V8: Use Detected Level or Default
                    "entity_type": "program",
                    "source_type": "pdf_only",
                    "faculty_uid": faculty_uid, # V8: True UID
                    "faculty_slug": slug,      # V8: Convenience Slug
                    "run_id": self.run_id,
                    "run_id": self.run_id,
                    "scraped_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "source_url": pdf_url,
                    "text_for_embedding": (
                        f"Programul: {row['program_name']} ({row.get('level', 'Master')})\n"
                        f"Facultate: {slug.upper()}\n"
                        f"Locuri Buget: {row['spots_budget']} (Sursa: PDF {pdf_url})\n"
                        f"Locuri Taxa: {row['spots_tax']} (Sursa: PDF {pdf_url})\n"
                        f"Admitere: Media Licență\n"
                        f"[INFERENCE]\n"
                        f"Cariera: {', '.join(career_paths)}"
                    ),
                    "metadata": {"original_pdf": pdf_url},
                    "career_paths": career_paths,
                    "admission_year": self.admission_year
                }
                self._save_program(slug, prog)
            return

        matcher = RomanianProgramMatcher(programs, filtered_rows)
        results = matcher.match_all()
        
        for res in results:
            prog = res["program"]
            match = res["match"]
            score = res["score"]
            status = res["status"]
            
            html_name = prog["name"]
            
            # V8: Ensure IDs are consistent even for HTML programs
            prog["faculty_uid"] = faculty_uid
            prog["faculty_slug"] = slug
            
            if match and score > 0.65: # New threshold for weighted score
                match_name = match["program_name"]
                logger.info(f"Match ({status}): '{html_name}' <-> '{match_name}' ({score:.2f})")
                
                if status == "ambiguous":
                    logger.warning(f"  [AMBIGUOUS] Check manually: {html_name}")
                
                # UPDATE PROGRAM
                # V8.7: Evidence Collection
                prog["evidence"] = prog.get("evidence", {})
                prog["evidence"]["spots"] = prog["evidence"].get("spots", [])
                
                evidence_entry = {
                    "source": pdf_url,
                    "source_name": source_name,
                    "value": {"budget": match.get("spots_budget", 0), "tax": match.get("spots_tax", 0)},
                    "score": likelihood_score, # Content score of the PDF
                    "match_score": score, # Fuzzy match score
                    "timestamp": datetime.datetime.now().isoformat()
                }
                prog["evidence"]["spots"].append(evidence_entry)
                
                # Arbitrate: Pick Highest Score (Content + Match)
                # Simple logic: If this match is better than current 'source_score', overwrite.
                current_score = prog.get("metadata", {}).get("best_source_score", -999)
                this_total_score = likelihood_score + (score * 10) # Weighted
                
                if this_total_score > current_score:
                    prog["spots_budget"] = match.get("spots_budget", 0)
                    prog["spots_tax"] = match.get("spots_tax", 0)
                    
                    prog["metadata"] = prog.get("metadata", {})
                    prog["metadata"]["best_source_score"] = this_total_score
                    prog["metadata"]["pdf_match_score"] = score
                    prog["metadata"]["pdf_match_name"] = match_name
                    prog["metadata"]["pdf_source"] = pdf_url
                    prog["metadata"]["match_status"] = status
                    
                    # Update Embedding Text
                    career_paths = prog.get("career_paths", self._infer_career_paths(html_name))
                    prog["text_for_embedding"] = (
                        f"Programul: {html_name} ({prog.get('level', 'Master')})\n"
                        f"Facultate: {slug.upper()}\n"
                        f"Locuri Buget: {match.get('spots_budget', 0)} (Sursa: PDF {source_name})\n"
                        f"Locuri Taxa: {match.get('spots_tax', 0)} (Sursa: PDF {source_name})\n"
                        f"[INFERENCE]\n"
                        f"Cariera: {', '.join(career_paths)}"
                    )

                self._save_program(slug, prog)
            else:
                logger.info(f"No match for '{html_name}' (Best Score: {score:.2f})")
                
            # V8.6: Fuse Grades (Independent of Spots Match)
            if grades_map:
                # Simple heuristic: Fuzzy match program name vs grade keys
                best_g_key = None
                best_g_score = 0
                html_norm = self._romanian_normalize(html_name)
                
                for g_key in grades_map:
                    g_norm = self._romanian_normalize(g_key)
                    g_score = fuzz.token_set_ratio(html_norm, g_norm)
                    if g_score > 85 and g_score > best_g_score:
                        best_g_score = g_score
                        best_g_key = g_key
                        
                if best_g_key:
                    grade_val = grades_map[best_g_key]
                    prog["last_admission_grade"] = grade_val
                    prog["metadata"] = prog.get("metadata", {})
                    prog["metadata"]["grade_source"] = best_g_key
                    # Append to embedding
                    prog["text_for_embedding"] = (prog.get("text_for_embedding") or "") + f"\nUltima Medie ({self.admission_year-1}): {grade_val:.2f}"
                    self._save_program(slug, prog)

    def _infer_career_paths(self, program_name: str) -> List[str]:
        """Simple heuristic for career paths based on keywords."""
        mapping = {
            "agricultura": ["Inginer Agronom", "Fermier", "Consultant Agricol"],
            "montanologie": ["Inginer Montan", "Ranger", "Expert Dezvoltare Rurală"],
            "cadastru": ["Inginer Cadastru", "Topograf", "Geodez"],
            "biologie": ["Biolog", "Cercetător", "Profesor"],
            "peisagistic": ["Arhitect Peisagist", "Designer Grădini"],
            "alimentar": ["Inginer Industrie Alimentară", "Controlor Calitate"],
            "horticultur": ["Horticultor", "Manager Fermă"],
            "silvicultur": ["Inginer Silvic", "Pădurar"],
            "mediu": ["Ecolog", "Inspector Protecția Mediului"],
            "management": ["Manager Proiect", "Administrator"]
        }
        name_lower = program_name.lower()
        for key, paths in mapping.items():
            if key in name_lower:
                return paths
        return ["Specific domeniului"]

    def _save_program(self, slug: str, program: Dict):
        # Overwrite file
        path = self.base_dir / "raw" / slug / "programs" / f"{program['uid']}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(program, f, indent=2, ensure_ascii=False)

    def _save_quarantine(self, slug: str, row: Dict, val_res: Dict):
        q_dir = self.base_dir / "raw" / slug / "quarantine"
        q_dir.mkdir(parents=True, exist_ok=True)
        
        uid = hashlib.sha256(row['program_name'].encode()).hexdigest()
        item = {
            "name": row['program_name'],
            "reason": val_res['reason'],
            "score": val_res['score'],
            "raw_row": row
        }
        with open(q_dir / f"{uid}.json", "w", encoding="utf-8") as f:
            json.dump(item, f, indent=2, ensure_ascii=False)

    def _romanian_normalize(self, text: str) -> str:
        if not text: return ""
        text = text.lower()
        text = text.replace("ş", "s").replace("ș", "s").replace("ţ", "t").replace("ț", "t")
        text = text.replace("ă", "a").replace("â", "a").replace("î", "i")
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split())

if __name__ == "__main__":
    # Test
    # Need run ID
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python matcher.py <run_id>")
        sys.exit(1)
    
    engine = DataFusionEngine(sys.argv[1])
    engine.enrich_run()
