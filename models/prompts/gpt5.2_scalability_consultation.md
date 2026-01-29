# GPT-5.2 Pro Consultation: Scalability Architecture

**Role**: You are the Senior System Architect advising on a Python-based university scraping platform.

**Current State**:
- We have a working pipeline for **1 University** (University of Craiova - "UCV") with multiple faculties.
- **Tech Stack**:
    - `crawl4ai` (HTML) + `pdfplumber` (PDF)
    - `pydantic` models (strict schema)
    - `rapidfuzz` (fuzzy matching validation)
    - `DataFusionEngine` (merges HTML & PDF sources)
- **Architecture**:
    - `UniversityAdapter` interface (see below) is designed to standardize scraping across different sites.
    - We currently instantiate `UCVAdapter` which implements this interface.

**The Challenge**:
We need to scale from **1 University** to **50+ Universities** (approx. 200+ faculties).
Each university has unique layouts, inconsistent PDF formats, and different "spots" terminologies.

**Specific Questions for You**:
1.  **Factory Pattern**: How should we structure the project to manage 50+ adapter files? (e.g., `execution/scrapers/{uni_slug}/adapter.py` vs a plugin system?)
2.  **Configuration vs Code**: Should we try to move selector logic (CSS/XPath) into YAML config files to minimize code, or stay with Python classes for flexibility?
3.  **Resilience**: With 50 concurrent scrapers (or sequential), how do we handle shared resources (browser instances) and rate limiting without a complex queueing infrastructure (like Celery/Redis) if we want to keep it simple?
4.  **Adapter Interface Review**: Please review the provided `UniversityAdapter` interface. Is it abstract enough? Are we missing methods for "Pagination" or "Authentication" that might pop up later?

**Attached Context Files**:
Please analyze the following 10 uploaded files which represent the core of our system:

1.  **Contract**: `execution/scrapers/adapter_interface.py` (The Abstract Base Class)
2.  **Implementation**: `execution/scrapers/ucv/adapter.py` (How UCV implements the contract)
3.  **Engine**: `execution/base/scraper_base.py` (The logic running the scraping loop)
4.  **Logic**: `execution/enrichment/matcher.py` (Fuzzy matching & conflict arbitration)
5.  **PDFs**: `execution/scrapers/ucv/pdf_parser.py` (Page-by-page extraction logic)
6.  **Data**: `execution/models/program.py` (Pydantic models)
7.  **Quality**: `execution/processors/validator.py` ("Iron Dome" Semantic Validator)
8.  **Config**: `execution/scrapers/ucv/config.yaml` (Faculty definitions)
9.  **Orchestration**: `run_pipeline_v4.py` (How we currently run a job)
10. **History**: `task.md` (What we have just finished)

**Output Desired**:
Based *specifically* on these files, provide a strategic roadmap for the "Scalability Phase":
1.  **Architecture**: Critique the `UniversityAdapter`. Is it robust enough for 50 universities?
2.  **Factory Pattern**: How to manage 50+ adapter class files dynamically?
3.  **Config vs Code**: Should we move more logic (selectors) to YAML?
4.  **Concurrency**: Recommendation for running these 50 scrapers (AsyncIO vs Celery)?
