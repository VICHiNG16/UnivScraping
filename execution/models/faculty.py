from typing import Optional, List
from pydantic import Field
from execution.models.base import BaseEntity

class Faculty(BaseEntity):
    """
    Represents a University Faculty.
    """
    name: str = Field(..., description="Official name of the faculty.")
    slug: str = Field(..., description="URL-friendly slug (e.g., 'facultatea-de-automatica').")
    description: Optional[str] = Field(None, description="Brief description or intro text.")
    dean: Optional[str] = Field(None, description="Name of the Dean.")
    
    # We store program UIDs to keep entities decoupled in storage.
    # The relationship is reconstructed during CSV export.
    program_uids: List[str] = Field(default_factory=list, description="List of UIDs of programs offered by this faculty.")
    
    def __init__(self, **data):
        # Force entity_type to 'faculty'
        data['entity_type'] = 'faculty'
        super().__init__(**data)
