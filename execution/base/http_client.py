import requests
import time
import random
import logging
from typing import Optional, List, Dict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Default User-Agent list
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

class PoliteHTTPClient:
    """
    HTTP Client that enforces politeness (delays) and reliability (retries, rotation).
    """
    def __init__(self, 
                 user_agents: List[str] = None, 
                 min_delay: float = 1.0, 
                 max_delay: float = 3.0,
                 max_retries: int = 3):
        self.user_agents = user_agents or DEFAULT_USER_AGENTS
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.session = self._init_session(max_retries)
        self.logger = logging.getLogger("infrastructure.http_client")

    def _init_session(self, max_retries: int) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _get_random_header(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7"
        }

    def _sleep(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)

    def get(self, url: str, timeout: int = 60) -> requests.Response:
        """
        Execute a polite GET request.
        """
        self._sleep()
        headers = self._get_random_header()
        
        self.logger.debug(f"Fetching: {url}")
        try:
            response = self.session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch {url}: {e}")
            raise e
