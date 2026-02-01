import logging
import sys
import os
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
import re

# Ensure execution modules are in path
sys.path.append(os.getcwd())

from execution.scrapers.ucv.pdf_parser import PDFParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_parser")

def debug_spots(pdf_path):
    print(f"\n--- Debugging SPOTS for {pdf_path} ---")

    parser = PDFParser()
    try:
        # Monkey patch to capture OCR text
        original_ocr = parser._ocr_pdf_to_text
        def captured_ocr(path):
            text = original_ocr(path)
            print("\n--- OCR CAPTURED TEXT (FULL) ---")
            print(text)
            print("--- END OCR PREVIEW ---\n")
            return text
        parser._ocr_pdf_to_text = captured_ocr

        results = parser.extract_spots(pdf_path)
        print(f"Found {len(results)} rows:")
        for r in results:
            print(r)

    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_pdf_parsing.py [pdf_path]")
        sys.exit(1)

    path = sys.argv[1]
    debug_spots(path)
