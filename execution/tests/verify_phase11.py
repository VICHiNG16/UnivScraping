
import unittest
import datetime
from execution.scrapers.factory import ScraperFactory
from execution.enrichment.pdf_ranker import PDFTruthRanker

class TestPhase11(unittest.TestCase):
    def test_factory_load_ucv(self):
        """Verify ScraperFactory loads UCVAdapter correctly."""
        print("\nTesting ScraperFactory.get_adapter('ucv')...")
        adapter = ScraperFactory.get_adapter("ucv")
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.get_university_slug(), "ucv")
        print("✅ Factory loaded UCVAdapter successfully.")

    def test_pdf_ranker_scoring(self):
        """Verify PDFTruthRanker logic."""
        print("\nTesting PDFTruthRanker scoring...")
        ranker = PDFTruthRanker(admission_year=2026)
        
        candidates = [
            {"link_text": "Ghid Admitere", "pdf_url": "guide.pdf"}, # Low value
            {"link_text": "Cifra de Scolarizare 2026", "pdf_url": "spots.pdf"}, # High value
            {"link_text": "Grile Exam", "pdf_url": "grile.pdf"}, # Negative value
            {"link_text": "Cifra 2025", "pdf_url": "old.pdf"} # Backup year
        ]
        
        ranked = ranker.rank_candidates(candidates)
        
        # Top should be Cifra 2026
        self.assertIn("2026", ranked[0]["link_text"])
        self.assertGreater(ranked[0]["stage_a_score"], ranked[1]["stage_a_score"])
        
        # Bottom should be Grile
        self.assertIn("Grile", ranked[-1]["link_text"])
        self.assertLess(ranked[-1]["stage_a_score"], 0)
        
        print(f"✅ Ranker Order: {[r['link_text'] for r in ranked]}")

if __name__ == "__main__":
    unittest.main()
