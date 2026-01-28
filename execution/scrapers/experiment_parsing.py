from execution.scrapers.ucv.pdf_parser import PDFParser

# Target the specific PDF identified as "repartizare locuri"
PDF_PATH = r"data/runs/ucv_20260128T154115/raw/ace/pdf_vault/e5c953eaf313c4be.pdf"

if __name__ == "__main__":
    parser = PDFParser()
    print(f"--- PARSING {PDF_PATH} ---")
    data = parser.extract_spots(PDF_PATH)
    print(f"Extracted {len(data)} items:")
    for item in data:
        print(item)
