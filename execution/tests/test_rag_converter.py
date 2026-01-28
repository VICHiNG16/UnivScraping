
import unittest
import json
import shutil
from pathlib import Path
from execution.processors.rag_converter import RAGSchemaConverter

class TestRAGConverter(unittest.TestCase):
    def setUp(self):
        self.test_run_id = "test_run_rag"
        self.base_dir = Path(f"data/runs/{self.test_run_id}/raw/ace/programs")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.program_data = {
            "entity_type": "program",
            "uid": "1234567890abcdef",
            "name": "Calculatoare (în limba engleză)",
            "faculty_uid": "ace",
            "level": "Licenta",
            "duration_years": "4 ani",
            "spots_budget": 20,
            "spots_tax": 10
        }
        
        with open(self.base_dir / "prog1.json", "w", encoding="utf-8") as f:
            json.dump(self.program_data, f)
            
    def tearDown(self):
        shutil.rmtree(f"data/runs/{self.test_run_id}", ignore_errors=True)

    def test_enrichment(self):
        converter = RAGSchemaConverter()
        output_file = Path(f"data/runs/{self.test_run_id}/rag_out.json")
        
        converter.convert_run(self.test_run_id, str(output_file))
        
        self.assertTrue(output_file.exists())
        
        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.assertEqual(len(data), 1)
        doc = data[0]
        
        # Verify RAG fields
        self.assertEqual(doc["language"], "en") # Should detect from "engleză"
        self.assertIn("computer science", doc["keywords"]) # Domain expansion
        self.assertIn("international", doc["keywords"])
        self.assertTrue(doc["text_for_embedding"].startswith("Program de studii Calculatoare"))
        self.assertEqual(doc["program_id"], "ucv_1234567890ab")

if __name__ == "__main__":
    unittest.main()
