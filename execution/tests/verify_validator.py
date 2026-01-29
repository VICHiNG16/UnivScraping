
import unittest
import logging
from execution.processors.validator import SemanticValidator

logger = logging.getLogger("verify_validator")

class TestSemanticValidator(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.INFO)
        self.validator = SemanticValidator()

    def test_valid_programs(self):
        valid_examples = [
            "Ingineria Sistemelor",
            "Calculatoare si Tehnologia Informatiei",
            "Drept",             # Short but keyword
            "Management",
            "Psihologie",        # Suffixed (ologie)
            "Kinetoterapie",     # Keyword
            "Limba si Literatura Romana"
        ]
        for name in valid_examples:
            res = self.validator.validate_program_name(name)
            self.assertEqual(res["status"], "PASS", f"Should PASS: {name} (Score: {res['score']}, Reason: {res['reason']})")
            logger.info(f"✅ PASS: {name} ({res['score']})")

    def test_garbage(self):
        garbage_examples = [
            "Secretariat",
            "Meniu Principal",
            "Acasa",
            "Contact",
            "Programul de la ora 10", 
            "aaaaa",             # Low entropy
            "123456",            # Digit ratio
            "Pagina 1 din 10"    # Generic
        ]
        for name in garbage_examples:
            res = self.validator.validate_program_name(name)
            self.assertNotEqual(res["status"], "PASS", f"Should FAIL: {name} (Score: {res['score']}, Reason: {res['reason']})")
            logger.info(f"✅ FAIL: {name} ({res['reason']})")

    def test_normalization(self):
        # "Științe" should match "stiint"
        res = self.validator.validate_program_name("Științe Politice")
        self.assertEqual(res["status"], "PASS", "Should handle diacritics")
        logger.info(f"✅ PASS: Științe ({res['score']})")

if __name__ == '__main__':
    unittest.main()
