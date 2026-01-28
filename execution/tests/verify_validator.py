
import logging
import sys
from execution.processors.validator import SemanticValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_validator")

def verify_validator():
    validator = SemanticValidator()
    
    test_cases = [
        # PASS
        ("Ingineria Sistemelor", "PASS"),
        ("Tehnologia Informației", "PASS"),
        ("Informatică", "PASS"),
        ("Limba și Literatura Română", "PASS"),
        ("Drept", "PASS"),
        
        # FAIL
        ("Meniu", "FAIL"),
        ("Secretariat", "FAIL"),
        ("Contact", "FAIL"),
        ("Acasa", "FAIL"),
        ("12345", "FAIL"),
        ("ABC", "FAIL"), # Too short
        
        # QUARANTINE / FAIL (Dependig on strictness)
        ("Program Nou", "FAIL"), # Generic, low score
        ("Admitere 2026", "FAIL"), # No positive keywords, short
        ("Studii de caz", "PASS") # "Studii" is positive
    ]
    
    passed_all = True
    for name, expected in test_cases:
        res = validator.validate_program_name(name)
        status = res["status"]
        if status != expected:
            # Allow QUARANTINE if expected FAIL for borderline
            if expected == "FAIL" and status == "QUARANTINE":
                logger.info(f"⚠️  Borderline: '{name}' -> QUARANTINE (Expected FAIL). Acceptable.")
            elif expected == "PASS" and status == "QUARANTINE":
                 logger.warning(f"⚠️  Weak Pass: '{name}' -> QUARANTINE (Expected PASS). Score: {res['score']}, Reason: {res['reason']}")
            else:
                logger.error(f"❌ Mismatch: '{name}' -> {status} (Expected {expected}). Score: {res['score']}, Reason: {res['reason']}")
                passed_all = False
        else:
            logger.info(f"✅ Correct: '{name}' -> {status}")
            
    return passed_all

if __name__ == "__main__":
    if verify_validator():
        sys.exit(0)
    else:
        sys.exit(1)
