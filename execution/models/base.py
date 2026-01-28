from pydantic import BaseModel
from execution.models.provenance import ProvenanceMixin

class BaseEntity(ProvenanceMixin):
    """
    Base class for all scraped entities (Faculties, Programs).
    Inherits strict provenance fields (uid, run_id, etc.)
    """
    pass
