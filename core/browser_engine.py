"""
HunterAI - Browser Automation Engine
Playwright-based browser control for automated web testing.
Handles navigation, form filling, screenshot capture, and intelligent fuzzing.
"""

import os
import asyncio
import json
import threading
from datetime import datetime, timezone

from config import ASSETS_DIR


class BrowserEngine:
    """Playwright-based browser automation for web vulnerability testing."""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self._initialized = False
        self._lock = threading.Lock()

    async def initialize(self):
        """Initialize Playwright browser."""
        if self._initialized:
            return

        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            self.page = await self.context.new_page()
            self._initialized = True
        except Exception as e:
            self._initialized = False
            raise RuntimeError(f"Failed to initialize browser: {e}")

    async def navigate(self, url):
        """Navigate to a URL and return page info."""
        if not self._initialized:
            await self.initialize()

        try:
            response = await self.page.goto(url, wait_until="networkidle", timeout=30000)
            return {
                "url": self.page.url,
                "title": await self.page.title(),
                "status": response.status if response else None,
                "headers": dict(response.headers) if response else {}
            }
        except Exception as e:
            return {"error": str(e), "url": url}

    async def screenshot(self, path=None, full_page=False):
        """Take a screenshot of the current page."""
        if not self._initialized:
            return None

        if not path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(ASSETS_DIR, f"screenshot_{timestamp}.png")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        await self.page.screenshot(path=path, full_page=full_page)
        return path

    async def get_page_info(self):
        """Get comprehensive information about the current page."""
        if not self._initialized:
            return {}

        info = {
            "url": self.page.url,
            "title": await self.page.title(),
        }

        # Get forms
        forms = await self.page.evaluate("""() => {
            return Array.from(document.querySelectorAll('form')).map(form => ({
                action: form.action,
                method: form.method,
                inputs: Array.from(form.querySelectorAll('input, textarea, select')).map(input => ({
                    name: input.name,
                    type: input.type,
                    id: input.id,
                    placeholder: input.placeholder
                }))
            }));
        }""")
        info["forms"] = forms

        # Get links
        links = await self.page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href]')).map(a => ({
                href: a.href,
                text: a.textContent.trim().substring(0, 100)
            })).filter(l => l.href.startsWith('http'));
        }""")
        info["links"] = links

        # Get meta tags
        meta = await self.page.evaluate("""() => {
            return Array.from(document.querySelectorAll('meta')).map(m => ({
                name: m.name || m.getAttribute('property'),
                content: m.content
            })).filter(m => m.name);
        }""")
        info["meta"] = meta

        # Get technology hints
        tech = await self.page.evaluate("""() => {
            const hints = {};
            const gen = document.querySelector('meta[name="generator"]');
            if (gen) hints.generator = gen.content;
            if (window.jQuery) hints.jquery = jQuery.fn.jquery;
            if (window.React) hints.react = true;
            if (window.Vue) hints.vue = true;
            if (window.angular) hints.angular = true;
            if (window.ng) hints.angular = true;
            return hints;
        }""")
        info["technology_hints"] = tech

        return info

    async def fill_form(self, selector, value):
        """Fill a form field."""
        if not self._initialized:
            return False
        try:
            await self.page.fill(selector, value)
            return True
        except Exception:
            return False

    async def click(self, selector):
        """Click an element."""
        if not self._initialized:
            return False
        try:
            await self.page.click(selector)
            return True
        except Exception:
            return False

    async def get_cookies(self):
        """Get all cookies for the current page."""
        if not self._initialized:
            return []
        return await self.context.cookies()

    async def get_headers(self, url):
        """Get response headers for a URL."""
        if not self._initialized:
            await self.initialize()
        try:
            response = await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            return dict(response.headers) if response else {}
        except Exception:
            return {}

    async def crawl_links(self, base_url, max_depth=2):
        """Crawl the page and discover all links."""
        if not self._initialized:
            await self.initialize()

        discovered = set()
        to_visit = [(base_url, 0)]
        visited = set()

        while to_visit:
            url, depth = to_visit.pop(0)
            if url in visited or depth > max_depth:
                continue

            visited.add(url)
            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
                links = await self.page.evaluate("""(baseUrl) => {
                    return Array.from(document.querySelectorAll('a[href]'))
                        .map(a => a.href)
                        .filter(href => href.startsWith(baseUrl));
                }""", base_url)

                for link in links:
                    discovered.add(link)
                    if depth + 1 <= max_depth:
                        to_visit.append((link, depth + 1))
            except Exception:
                continue

        return list(discovered)

    async def close(self):
        """Close the browser."""
        if self.browser:
            await self.browser.close()
        if hasattr(self, "_playwright") and self._playwright:
            await self._playwright.stop()
        self._initialized = False


# Wrapper to run async browser operations from sync code
def run_browser_task(coro):
    """Run an async browser task from synchronous code."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# Singleton
browser_engine = BrowserEngine()
