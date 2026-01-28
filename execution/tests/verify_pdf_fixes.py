
import logging
import sys
import os
import re
from unittest import mock
from execution.scrapers.ucv.pdf_parser import PDFParser

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_pdf_fixes")

def verify_fixes():
    parser = PDFParser()
    
    # 1. Mock Data: Multi-page, Hyphenated Text
    mock_pages = [
        # Page 0: Hyphenation (Matches P1)
        "Programul: Ingineria si\nProtectia Med-\niului\nLocuri buget: 10\nLocuri taxa: 5",
        
        # Page 1: Line break split without hyphen (Matches P1)
        # Note: "Locu-\nri" checking generic hyphen too?
        "Specializarea: Tehnologia\nInformatiei\nLocuri buget: 20\nLocuri taxa: 10",
        
        # Page 2: Standard Line Item (Matches P2 regex: ^Name \d+ loc)
        "Cibernetica 30 loc buget 15 loc tax\nInformatica 50 loc buget 20 loc tax"
    ]
    
    # Mocking pdfplumber is hard, so we'll test the Logic directly by subclassing or mocking open
    # But `_extract_via_text` calls `pdfplumber.open`.
    # Easier: Mock the `open` call to return a mock object with pages
    
    with mock.patch("pdfplumber.open") as mock_open:
        mock_pdf = mock.Mock()
        mock_pdf.pages = [mock.Mock() for _ in mock_pages]
        for i, page_mock in enumerate(mock_pdf.pages):
            page_mock.extract_text.return_value = mock_pages[i]
        
        mock_open.return_value.__enter__.return_value = mock_pdf
        
        # Run Extraction
        results = parser._extract_via_text("dummy.pdf")
        
        # Verify Results
        found_mediu = False
        found_tehno = False
        found_ciber = False
        
        for r in results:
            name = r["program_name"]
            page = r.get("page")
            logger.info(f"Extracted: '{name}' (Page {page})")
            
            if "Ingineria si Protectia Mediului" in name: # "Med-iului" -> "Mediului"
                found_mediu = True
                if page != 1: logger.error("Checking Page Provenance... Failed (Expected 1)")
            
            if "Tehnologia Informatiei" in name: # "Tehnologia\nInformatiei" -> "Tehnologia Informatiei"
                found_tehno = True
                if page != 2: logger.error("Checking Page Provenance... Failed (Expected 2)")
                
            if "Cibernetica" in name:
                found_ciber = True
                if page != 3: logger.error("Checking Page Provenance... Failed (Expected 3)")

        if not found_mediu:
            logger.error("❌ FAILED: Hyphenation 'Med-iului' not fixed.")
            
        if not found_tehno:
            logger.error("❌ FAILED: Newline 'Tehnologia\\nInformatiei' not fixed.")
            
        if not found_ciber:
             logger.error("❌ FAILED: Standard extraction broken.")
             
        if found_mediu and found_tehno and found_ciber:
            logger.info("✅ SUCCESS: All patterns extracted and normalized correctly.")
            return True
            
    return False

if __name__ == "__main__":
    if verify_fixes():
        sys.exit(0)
    else:
        sys.exit(1)
