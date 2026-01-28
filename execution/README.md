# Execution Scripts

This folder contains the **Layer 3: Execution** tools of the agent architecture.

## Principles
1.  **Deterministic**: Scripts should produce the same output for the same input (mostly).
2.  **Single Responsibility**: One script does one thing well (e.g., `scrape_single_site.py`, `parse_pdf.py`).
3.  **Self-Contained**: Scripts should import what they need and manage their own dependencies/paths relative to the project root.
4.  **Error Handling**: Fail gracefully with informative error messages that the agent can read to "self-anneal".

## Environment Variables
Store API keys and secrets in `.env` in the project root.
Use `python-dotenv` to load them:

```python
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("API_KEY")
```

## Structure
- Input: Command line arguments or config files.
- Output: Files in `.tmp/` or specific deliverables.
