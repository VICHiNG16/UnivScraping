from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, validator
import hashlib
import re

class ProvenanceMixin(BaseModel):
    """
    Mixin to strictly track where data came from and when.
    Enforces SHA256 UIDs based on canonical URLs.
    """
    uid: str = Field(..., description="Stable SHA256 hash of the canonical source URL.")
    run_id: str = Field(..., description="The session ID this record belongs to.")
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_url: str = Field(..., description="Canonical source URL.")
    content_hash: str = Field(..., description="SHA256 hash of the content (for change detection).")
    entity_type: str = Field(..., description="Type of entity: 'faculty' or 'program'.")

    @staticmethod
    def canonicalize_url(url: str) -> str:
        """
        Return a strictly canonicalized URL:
        - Strip whitespace
        - Lowercase scheme/netloc
        - Remove default ports
        - Remove tracking params (utm_*, fbclid, etc.)
        - Sort query params
        - Remove fragment
        """
        if not url: return ""
        url = url.strip()
        try:
            from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
            
            parsed = urlparse(url)
            scheme = parsed.scheme.lower() or "https"
            netloc = parsed.netloc.lower()
            if ":80" in netloc: netloc = netloc.replace(":80", "")
            if ":443" in netloc: netloc = netloc.replace(":443", "")
            
            # Filter tracking params
            img_query = parse_qsl(parsed.query)
            exclude_prefixes = ("utm_", "fbclid", "gclid", "ref")
            filtered_query = [(k, v) for k, v in img_query if not k.lower().startswith(exclude_prefixes)]
            sorted_query = sorted(filtered_query)
            
            new_query = urlencode(sorted_query)
            path = parsed.path.rstrip("/") # Consistent trailing slash handling
            
            return urlunparse((scheme, netloc, path, "", new_query, ""))
        except Exception:
            return url.strip() # Fallback

    @staticmethod
    def normalize_name(text: str) -> str:
        """
        Slugify name for stable ID generation. 
        Removes: diacritics, parens, years, extra whitespace.
        Example: "Inginerie (2024)" -> "inginerie"
        """
        if not text: return ""
        import unicodedata
        # Lowercase
        text = text.lower()
        # Remove years/parens (volatile info)
        text = re.sub(r'\(.*?\)', '', text)
        text = re.sub(r'\d{4}', '', text)
        # Normalize unicode (diacritics)
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
        # Replace non-alphanumeric with hyphen
        text = re.sub(r'[^a-z0-9]+', '-', text)
        return text.strip("-")

    @staticmethod
    def generate_uid(source_string: str) -> str:
        """
        Generate a stable SHA256 UID.
        Args:
            source_string: Input string (e.g., canonical_url or "url|program_name").
        """
        return hashlib.sha256(source_string.encode('utf-8')).hexdigest()

    @staticmethod
    def generate_content_hash(content: str) -> str:
        """Generate SHA256 hash of content (text/html) for change detection."""
        if content is None:
            return ""
        # Normalize newlines to avoid OS differences affecting hash
        normalized = content.replace('\r\n', '\n').strip()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
