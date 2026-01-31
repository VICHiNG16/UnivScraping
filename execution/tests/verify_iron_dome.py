
import unittest
from bs4 import BeautifulSoup
from execution.enrichment.boilerplate import BoilerplateRejector

class TestIronDome(unittest.TestCase):
    def setUp(self):
        self.rejector = BoilerplateRejector()
        
    def test_navigation_rejection(self):
        html = """
        <nav>
            <ul>
                <li><a href="#">Home</a></li>
                <li><a href="#">Contact</a></li>
            </ul>
        </nav>
        """
        soup = BeautifulSoup(html, "html.parser")
        items = soup.find_all("li")
        for item in items:
            self.assertTrue(self.rejector.is_structural_garbage(item), f"Should reject nav item: {item.text}")
            
    def test_link_density_rejection(self):
        # High link density, short text
        html = """
        <li><a href="#">Termeni si Conditii</a></li>
        """
        soup = BeautifulSoup(html, "html.parser")
        item = soup.find("li")
        self.assertTrue(self.rejector.is_structural_garbage(item), "Should reject high density link")
        
    def test_valid_program(self):
        # Valid program text, low link density
        html = """
        <li>
            Informatica Aplicata - 100 locuri buget, 50 locuri taxa.
        </li>
        """
        soup = BeautifulSoup(html, "html.parser")
        item = soup.find("li")
        self.assertFalse(self.rejector.is_structural_garbage(item), "Should KEEP valid program")

if __name__ == "__main__":
    unittest.main()
