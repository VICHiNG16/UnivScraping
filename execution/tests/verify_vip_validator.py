
import unittest
from bs4 import BeautifulSoup
from execution.scrapers.ucv.adapter import UCVAdapter

class TestVIPValidator(unittest.TestCase):
    def setUp(self):
        self.adapter = UCVAdapter()
        
    def test_reject_garbage(self):
        # These are real garbage items from the failed ucv_final.json
        garbage_inputs = [
            "Modalități de admitere",
            "Tematică probă limba engleză",
            "Numărul de credite obţinute la absolvire",
            "Tematică interviu: aici",
            "Cifra de școlarizare", 
            "Acreditare programe de studii",
            "Companii care recomandă FACE",
            "Tel: +40 251 418 475",
            "Cercetare Prezentare Strategia de cercetare...",
            "Acorduri bilaterale"
        ]
        
        for text in garbage_inputs:
            # Wrap in <li> because extract_programs expects structure
            html = f"<ul><li>{text}</li></ul>"
            programs = self.adapter.extract_programs_from_html(html, "http://test.com", "test_fac")
            self.assertEqual(len(programs), 0, f"FAILED: Should have rejected '{text}'")
            
    def test_accept_valid_programs(self):
        valid_inputs = [
            "Automatică și Informatică Aplicată - 20 locuri buget", # Has spots
            "Master în Securitate Cibernetică", # Whitelisted keywords
            "Inginerie Civilă", # Whitelisted
            "Drept European" # Whitelisted
        ]
        
        for text in valid_inputs:
             html = f"<ul><li>{text}</li></ul>"
             programs = self.adapter.extract_programs_from_html(html, "http://test.com", "test_fac")
             self.assertEqual(len(programs), 1, f"FAILED: Should have accepted '{text}'")

if __name__ == "__main__":
    unittest.main()
