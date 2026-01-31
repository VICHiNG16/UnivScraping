
import json
import logging
from pathlib import Path
from typing import List, Dict
import hashlib
from execution.models.program import Program

logger = logging.getLogger("rag_converter")

class RAGSchemaConverter:
    """
    Converts scraped Program entities into RAG-optimized documents.
    Generates embeddings text, keywords, and stable IDs.
    """
    def __init__(self, admission_year: int = None):
        import datetime
        self.admission_year = admission_year or datetime.datetime.now().year

    def convert_run(self, run_id: str, output_path: str = None):
        base_dir = Path(f"data/runs/{run_id}/raw")
        if not base_dir.exists():
            logger.error(f"Run {run_id} not found.")
            return

        all_programs = []
        
        # Traverse all faculty directories
        for faculty_dir in base_dir.iterdir():
            if not faculty_dir.is_dir(): continue
            
            prog_dir = faculty_dir / "programs"
            if not prog_dir.exists(): continue
            
            for p_file in prog_dir.glob("*.json"):
                with open(p_file, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        # Skip errors or non-programs
                        if data.get("entity_type") != "program": continue
                        
                        # Enrich
                        rag_doc = self._enrich_program(data)
                        all_programs.append(rag_doc)
                    except Exception as e:
                        logger.error(f"Error reading {p_file}: {e}")

        # Save Result
        if not output_path:
            output_path = f"data/runs/{run_id}/rag_dataset.json"
            
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_programs, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Saved {len(all_programs)} RAG documents to {output_path}")

    def _enrich_program(self, data: Dict) -> Dict:
        """
        Populate V4 fields with "Advisor-Grade" enrichment.
        """
        # 1. Normalize Language
        name_lower = data.get("name", "").lower()
        language = "ro"
        if "englez" in name_lower or "english" in name_lower:
            language = "en"
        elif "francez" in name_lower:
            language = "fr"
            
        # 2. Inferred Fields (Heuristics - Expanded V8)
        # 2. Inferred Fields (Heuristics - Expanded V8)
        from execution.models.ontology import CAREER_PATH_MAPPING
        mapping = CAREER_PATH_MAPPING
        
        career_paths = []
        for key, paths in mapping.items():
            if key in name_lower:
                career_paths.extend(paths)
                
        if not career_paths:
            career_paths = ["Specific domeniului"]
        else:
            career_paths = list(set(career_paths)) # Dedupe
        
        admission_reqs = ["Dosar (Medie Bac)"] # Default
        if "master" in str(data.get("level", "")).lower():
             admission_reqs = ["Media Licență (Probabil Interviu)"]

        # 3. Keywords
        keywords = ([data.get("name")] + 
                   [data.get("faculty_uid")] + 
                   data.get("name", "").lower().split())
        
        # Domain expansion
        if "calc" in name_lower: keywords.extend(["computer science", "it", "programare"])
        if "auto" in name_lower: keywords.extend(["control engineering", "robotics"])
        if language == "en": keywords.append("international")
        
        keywords = list(set([k.lower() for k in keywords if len(k) > 2]))

        # 4. Text for Embedding (Structure V8)
        # Split into Facts and Inferences for better retrieval
        
        facts_block = (
            f"Program: {data.get('name')}\n"
            f"Nivel: {data.get('level', 'Licenta')}\n"
            f"Facultate: {data.get('faculty_uid').upper()}\n"
            f"Durata: {data.get('duration_years', 'N/A')}\n"
            f"Limba: {language.upper()}\n"
            f"Locuri Buget ({self.admission_year}): {data.get('spots_budget', 'N/A')}\n"
            f"Locuri Taxa ({self.admission_year}): {data.get('spots_tax', 'N/A')}"
        )
        
        inferred_block = (
            f"Cariera: {', '.join(career_paths)}\n"
            f"Admitere: {', '.join(admission_reqs)}\n"
            f"Keywords: {', '.join(keywords)}"
        )
        
        narrative = f"[FACTS]\n{facts_block}\n\n[INFERRED]\n{inferred_block}\n\n[PROVENANCE]\nSource: {data.get('source_url', 'N/A')}"

        # 5. Stable ID
        rag_id = f"ucv_{data['faculty_uid']}_{data['uid'][:8]}"

        # Update Dict
        data["program_id"] = rag_id
        data["language"] = language
        data["keywords"] = keywords
        data["text_for_embedding"] = narrative
        data["admission_year"] = self.admission_year
        data["career_paths"] = career_paths
        
        return data

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python rag_converter.py <run_id>")
        sys.exit(1)
        
    converter = RAGSchemaConverter()
    converter.convert_run(sys.argv[1])
