from playwright.sync_api import sync_playwright, Browser, Page
from typing import Optional
import logging

class BrowserManager:
    """
    Singleton Wrapper for Playwright to prevent zombie processes.
    Uses sync API for simplicity in this script-based architecture.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
            cls._instance.playwright = None
            cls._instance.browser = None
            cls._instance.logger = logging.getLogger("infrastructure.browser")
        return cls._instance

    def start(self, headless: bool = True):
        if not self.playwright:
            self.logger.info("Starting Playwright...")
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=headless)

    def get_page(self) -> Page:
        if not self.browser:
            self.start()
        return self.browser.new_page()

    def get_html(self, url: str) -> str:
        """
        Fetch dynamic content.
        """
        page = self.get_page()
        try:
            page.goto(url, wait_until="networkidle")
            content = page.content()
            return content
        finally:
            page.close()

    def stop(self):
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
        self.logger.info("Playwright stopped.")
