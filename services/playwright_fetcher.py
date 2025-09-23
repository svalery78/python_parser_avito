from __future__ import annotations

import asyncio
import json
import os
from urllib.parse import urlparse
from pathlib import Path
from typing import Optional

from loguru import logger
from playwright.async_api import async_playwright, BrowserContext

from utils.headers import COOKIE_FILE, HeadersBuilder

BASE_DIR = Path(__file__).resolve().parents[1]


class PlaywrightFetcher:
    """Headless browser fetcher using Playwright with storage state cookies.

    Persists cookies in config/cookie.json and attempts to look like a real user.
    """

    def __init__(self, headless: bool = True, base_url: Optional[str] = None) -> None:
        env_headful = os.getenv("PW_HEADFUL", "0").lower() in {"1", "true", "yes"}
        self.headless = False if env_headful else headless
        self.base_url = base_url.rstrip("/") if base_url else None
        self.headers_builder = HeadersBuilder()

    def _make_url(self, path_or_url: str) -> str:
        if self.base_url and path_or_url.startswith("/"):
            return f"{self.base_url}{path_or_url}"
        return path_or_url

    async def _ensure_context(self, pw) -> BrowserContext:
        storage_state = None
        if COOKIE_FILE.exists():
            try:
                data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
                # Accept only valid cookie entries (need url starting with http(s) or domain field)
                if isinstance(data, dict) and isinstance(data.get("cookies"), list):
                    valid: list[dict] = []
                    for c in data["cookies"]:
                        if not isinstance(c, dict):
                            continue
                        url = c.get("url")
                        domain = c.get("domain")
                        if (isinstance(url, str) and url.startswith("http")) or isinstance(domain, str):
                            valid.append(c)
                    if valid:
                        storage_state = {"cookies": valid}
                # If the file is a simple dict name->value, skip applying as storage_state
            except Exception:
                storage_state = None

        # Proxy support from PROXY_URL if provided
        proxy = None
        proxy_url = os.getenv("PROXY_URL")
        if proxy_url:
            try:
                parsed = urlparse(proxy_url)
                proxy = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
                if parsed.username and parsed.password:
                    proxy.update({"username": parsed.username, "password": parsed.password})
            except Exception:
                proxy = None

        browser = await pw.chromium.launch(
            headless=self.headless,
            proxy=proxy,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        ua = self.headers_builder.build().get("user-agent")
        try:
            context = await browser.new_context(
                storage_state=storage_state,
                user_agent=ua,
                viewport={"width": 1366, "height": 768},
                locale="ru-RU",
                extra_http_headers={
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                },
            )
        except Exception:
            # Retry without storage state if invalid
            context = await browser.new_context(
                user_agent=ua,
                viewport={"width": 1366, "height": 768},
                locale="ru-RU",
                extra_http_headers={
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                },
            )

        # Stealth-like tweaks
        await context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """
        )
        return context

    async def get(self, path_or_url: str, wait_selector: Optional[str] = None, timeout_ms: int = 45000) -> str:
        url = self._make_url(path_or_url)
        async with async_playwright() as pw:
            context = await self._ensure_context(pw)
            page = await context.new_page()
            try:
                from playwright_stealth import stealth_async as _stealth_async
                await _stealth_async(page)
            except Exception:
                pass
            logger.debug(f"PW GET {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=timeout_ms)

            # Save cookies back
            try:
                state = await context.storage_state()
                COOKIE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as exc:
                logger.warning(f"Failed to save cookies: {exc}")

            content = await page.content()
            await context.close()
            return content


__all__ = ["PlaywrightFetcher"]


