
import importlib
from typing import Optional
from execution.scrapers.adapter_interface import UniversityAdapter

class ScraperFactory:
    """
    Factory to dynamically load University Adapters.
    """
    @staticmethod
    def get_adapter(university_slug: str) -> UniversityAdapter:
        try:
            # Dynamic import: execution.scrapers.{slug}.adapter
            module_path = f"execution.scrapers.{university_slug}.adapter"
            module = importlib.import_module(module_path)
            
            # Inspect module to find subclass of UniversityAdapter
            # Convention: Look for a class ending in 'Adapter' that isn't the base class
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, UniversityAdapter) and 
                    attr is not UniversityAdapter):
                    return attr()
            
            # Fallback: specific lookup for UCV
            if hasattr(module, "UCVAdapter"):
                return module.UCVAdapter()
                
            raise ValueError(f"No UniversityAdapter subclass found in {module_path}")
            
        except ImportError as e:
            raise ImportError(f"Could not load adapter for '{university_slug}'. Ensure 'execution/scrapers/{university_slug}/adapter.py' exists. Error: {e}")
