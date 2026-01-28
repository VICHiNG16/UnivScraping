from typing import Optional
from pydantic import Field
from execution.models.base import BaseEntity

class Program(BaseEntity):
    """
    Represents a Study Program (Specialization).
    """
    name: str = Field(..., description="Official name of the specialization.")
    faculty_uid: str = Field(..., description="Hashed UID of the parent faculty entity.")
    faculty_slug: str = Field(..., description="URL-friendly slug of the parent faculty (e.g. 'ace').")
    level: str = Field(..., description="Bachelor (Licenta), Master, PhD.")
    duration_years: Optional[str] = Field(None, description="Duration (e.g. '4 ani'). Stored as string to capture variants.")
    # V4 RAG Fields
    program_id: Optional[str] = Field(None, description="Stable ID for Vector DB.")
    language: Optional[str] = Field("Romanian", description="Language of instruction (normalized).")
    keywords: Optional[list[str]] = Field(default_factory=list, description="Search synonyms.")
    text_for_embedding: Optional[str] = Field(None, description="Narrative description for embedding.")
    admission_year: Optional[int] = Field(None, description="Year of admission stats.")
    
    # Admission stats (often from PDFs)
    spots_budget: Optional[int] = Field(None, description="Number of budget (free) spots.")
    spots_tax: Optional[int] = Field(None, description="Number of tuition-based spots.")
    
    # V3.2 Data Lineage fields
    spots_raw: Optional[str] = Field(None, description="Raw text for spots (e.g. '30 locuri') to prevent early validation loss.")
    source_type: str = Field("html", description="Source of data: 'html' (faculty page) or 'pdf' (admission doc).")
    accuracy_confidence: float = Field(0.5, description="0.0-1.0 score. HTML spots = low confidence. PDF table = high.")
    
    last_admission_grade: Optional[float] = Field(None, description="Last admission grade from previous year.")
    
    # Preservation of original raw text for debugging
    raw_admission_text: Optional[str] = Field(None, description="Raw string extracted for admission info (e.g. '30 locuri buget').")

    # V8.7 Conflict Modeling
    evidence: Optional[dict] = Field(default_factory=dict, description="Stores conflicting data points from multiple sources. Keys: 'spots', 'grades'.")

    def __init__(self, **data):
        # Force entity_type to 'program'
        data['entity_type'] = 'program'
        super().__init__(**data)
