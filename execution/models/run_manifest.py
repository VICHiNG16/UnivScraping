from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class RunManifest(BaseModel):
    """
    Metadata for a single scrape session (Run).
    Stored in data/runs/{run_id}/manifest.json.
    """
    run_id: str = Field(..., description="Unique ID for this run (e.g., ucv_20260128T120000).")
    university_code: str = Field(..., description="e.g., 'ucv'.")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    status: str = Field("running", description="'running', 'success', 'failed', 'partial'.")
    
    # Configuration Snapshot
    config_hash: str = Field(..., description="SHA256 of the config.yaml used.")
    
    # Statistics
    stats: Dict[str, int] = Field(
        default_factory=lambda: {
            "faculties_found": 0,
            "faculties_scraped": 0,
            "programs_found": 0,
            "programs_scraped": 0,
            "errors": 0,
            "snapshots_saved": 0
        }
    )
    
    # Error Index (High-level summary, details in errors/ folder)
    error_summary: List[Dict[str, str]] = Field(default_factory=list, description="List of {faculty: slug, error: msg}.")

    def complete(self, status: str = "success"):
        self.status = status
        self.completed_at = datetime.now(timezone.utc)
