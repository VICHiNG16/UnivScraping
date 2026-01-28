
import pdfplumber
import logging
import sys

# Windows console encoding fix
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"c:\Users\CALU\repos\antigravity\manual scraping\data\runs\verify_grades_20260128T214017\raw\ace\pdfs\results_bf6dd644.pdf"

print(f"Inspecting: {pdf_path}")
try:
    with pdfplumber.open(pdf_path) as pdf:
       page = pdf.pages[0]
       print("\n--- Page 1 Text (First 500 chars) ---")
       print(page.extract_text()[:500])
       
       print("\n--- Page 1 Tables ---")
       tables = page.extract_tables()
       if not tables:
           print("No tables found on Page 1.")
       for i, table in enumerate(tables):
           print(f"Table {i}:")
           # Print header and first row
           for row in table[:2]:
               print(row)
except Exception as e:
    print(f"Error: {e}")
