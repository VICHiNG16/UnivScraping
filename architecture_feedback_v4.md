# Architectural Feedback: Scaling the Universal University Scraper

**To:** Antigravity (AI Agent) & Engineering Team
**From:** Principal Software Architect
**Date:** October 26, 2023
**Subject:** Strategy for Scaling to 10+ Universities (Architecture V4)

## Executive Summary

The transition to a **Configuration-Driven Architecture** (Generic Adapter) is the correct strategic move to handle the N+1 problem of adding universities. However, relying solely on static CSS selectors for "Zero-Touch" scaling is brittle. The HTML of university sites is often legacy, inconsistent, and prone to silent structural changes.

To achieve true scale with minimal human intervention, we must move from **"Strict Extraction"** (brittle selectors) to **"Semantic Extraction"** (pattern matching & local-AI).

---

## 1. Automation: The "Discovery Agent"

**Challenge:** Automatically discovering CSS selectors to minimize human config writing.

### Recommendation: "Developer-Time" Discovery (The Architect Agent)

Do NOT attempt "Runtime Discovery" (finding selectors on every scrape) as a primary strategy. It is slow, costly, and risky for production data pipelines. Instead, build a **Discovery Agent** that runs *once* per university to generate the `config.yaml`.

#### Proposed Workflow:
1.  **Ingest**: Agent receives a URL (e.g., "https://.../admitere").
2.  **Fetch & Minimize**: Use `BrowserManager` to get the DOM. **Crucial**: Strip scripts, styles, and SVGs to reduce token count. Convert HTML to a simplified Markdown-like representation or "Skeleton HTML" before sending to the LLM.
    *   *Why?* Raw HTML is too token-heavy and noisy for LLMs to find precise patterns efficiently.
3.  **Pattern Recognition (LLM)**: Ask the LLM (Gemini/GPT-4): *"Identify the repeating element that contains a Program Name (text) and Spot Count (number). Return the CSS selector."*
4.  **Verification Loop**: The Agent immediately tries the suggested selector against the live page.
    *   *If 0 results:* Feedback loop -> "Selector failed. Try a broader container."
    *   *If success:* Save to `config.yaml`.

### Technical Tactic: The "Data-First" Search
Instead of looking for *tags* (`div > ul`), look for *data*.
*   **Heuristic**: Find the text "Taxa" or "Buget".
*   **Traversal**: Walk up the DOM tree from that text node until you hit a block-level element (`li`, `tr`, `div`) that also contains a program-like title.
*   **Generalization**: The class/tag of that parent element is your candidate selector.

---

## 2. Resilience: Bulletproofing the Generic Adapter

**Challenge:** HTML layouts change classes or structure, breaking strict selectors.

### Strategy A: The "Fallback Chain"
Your `config.yaml` should support a priority list of strategies, not just one selector.

```yaml
university_x:
  strategies:
    - type: "css_selector"
      selector: ".table-programs tr"
    - type: "visual_anchor"
      anchor_text: ["Locuri Buget", "Taxa"]
      container_tag: "tr"
    - type: "semantic_dom"
      pattern: "list_item_with_numbers"
```

### Strategy B: Semantic Anchors (The "Visual" Approach)
If the specific class `.row-program-active` disappears, the *visual relationship* usually remains.
*   **Logic**: "Find the text 'Informatica'. Look to the right (next DOM sibling or table cell) for a number."
*   **Implementation**: Use `BeautifulSoup`'s `find_next_sibling()` or `find_parent().find_all()` rather than absolute paths.

### Strategy C: Hybrid Parsing
Use the LLM as a backup parser.
*   **Workflow**: If standard extractors return 0 programs, grab the `<body>` text (markdown format) and send to LLM: *"Extract program names and spot counts as JSON from this text dump."*
*   **Cost Control**: Only trigger this if the "Bronze Layer" (provenance) shows the page *has* content (file size > 5KB) but "Silver Layer" extracted 0 entities.

---

## 3. Blind Spots & Complexities

**Challenge:** 50+ diverse sites (SPA, PDF-only, Messy HTML).

### A. The SPA (Single Page App) Trap
*   **Risk**: `requests.get()` returns valid HTTP 200 but the body is just `<div id="app"></div>`.
*   **Solution**:
    *   **Detection**: If `len(soup.get_text()) < 200` characters, flag as "Potentially Dynamic".
    *   **Escalation**: Automatically retry using `BrowserManager` (Playwright) to render the DOM.
    *   **Wait Strategy**: Don't just wait for `networkidle`. Wait for specific *content heuristics* (e.g., keywords "Licenta" or "Master" to appear in the DOM).

### B. The PDF "Wild West"
*   **Risk**: PDFs are not structured data. They are printed paper in digital format. Tables often lack headers on page 2, or use merged cells.
*   **Architecture**:
    1.  **Layout Analysis (`pdfplumber`)**: Superior to `pypdf` for table extraction because it preserves X/Y coordinates. Use it to detect "visual rows".
    2.  **Vision-Language Models (VLM)**: For the hardest 10% of PDFs (scanned, hand-written, complex grids), do not write code.
        *   *Action*: Convert PDF page to Image -> Send to Gemini 1.5 Pro / GPT-4V -> Prompt: *"Transcribe this table to JSON"*.
        *   *Trade-off*: Higher latency/cost, but solves the "impossible" cases instantly.

---

## 4. Validation at Scale (The "Iron Dome")

**Challenge:** Detecting "Silent Failures" (e.g., parser finds 0 spots, or data format changes).

### A. Historical Anomaly Detection (Z-Score)
*   **Logic**: A university's total spots rarely change by +/- 50% year-over-year.
*   **Check**: `abs(current_total_spots - last_year_total_spots) / std_dev > 2`.
*   **Action**: If triggered, **Block the Pipeline**. Do not promote to Gold Layer. Alert human.

### B. Cross-Referencing
*   If you extract data from HTML, cross-check it against the PDF "Regulation" document if available.
    *   *Example*: HTML says "Computer Science: 100 spots". PDF Regulation says "Total Faculty Spots: 50". Conflict detected -> Flag for review.

### C. The "Zero-Data" Panic
*   If a scraper runs successfully (no error code) but returns **0 programs**, this is a critical failure. Explicitly raise `EmptyExtractionError` unless the config marks the university as "Inactive".

---

## Summary of Next Steps for "Antigravity"

1.  **Refine `GenericAdapter`**: Implement the **Strategy Pattern** to support `css_selector`, `table_heuristic`, and `llm_fallback`.
2.  **Build `DiscoveryAgent`**: Create a script that takes a URL and outputs a candidate `config.yaml` block.
3.  **Upgrade Validation**: Implement the "Historical Anomaly" check in the Gold Layer.
