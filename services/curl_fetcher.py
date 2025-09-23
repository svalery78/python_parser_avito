from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

from curl_cffi import requests as curl
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from utils.headers import HeadersBuilder, load_cookies, save_cookies

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / "config"
COOKIE_FILE = CONFIG_DIR / "cookie.json"


class CurlCFFIFetcher:
    """HTTP fetcher using curl-cffi with browser impersonation to evade bot detection.

    - Uses Chrome impersonation and HTTP/2
    - Rotates realistic headers via HeadersBuilder
    - Persists cookies to config/cookie.json
    """

    def __init__(self, base_url: Optional[str] = None, headers_builder: Optional[HeadersBuilder] = None) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.headers_builder = headers_builder or HeadersBuilder()
        self.cookies = load_cookies()

    def _make_url(self, path_or_url: str) -> str:
        if self.base_url and path_or_url.startswith("/"):
            return f"{self.base_url}{path_or_url}"
        return path_or_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def get(
        self,
        path_or_url: str,
        headers_overrides: Optional[Dict[str, str]] = None,
        timeout: float = 45.0,
        proxy_url: Optional[str] = None,
    ) -> str:
        url = self._make_url(path_or_url)
        headers = self.headers_builder.build(headers_overrides)
        logger.debug(f"GET {url}")
        proxies = None
        proxy_url = proxy_url or os.getenv("PROXY_URL")
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}

        resp = curl.get(
            url,
            headers=headers,
            cookies=self.cookies or None,
            impersonate="chrome124",
            timeout=timeout,
            allow_redirects=True,
            proxies=proxies,
        )
        self._persist_response_cookies(resp)
        resp.raise_for_status()
        return resp.text

    def _persist_response_cookies(self, resp) -> None:
        try:
            jar = resp.cookies or {}
            cookies_dict: Dict[str, str] = {}
            if isinstance(jar, dict):
                cookies_dict = {str(k): str(v) for k, v in jar.items()}
            elif hasattr(jar, "items"):
                try:
                    cookies_dict = {str(k): str(v) for k, v in jar.items()}
                except Exception:
                    pass
            elif hasattr(jar, "__iter__"):
                # Could be a list of cookie objects or tuples
                for c in jar:
                    if hasattr(c, "name") and hasattr(c, "value"):
                        cookies_dict[str(c.name)] = str(c.value)
                    elif isinstance(c, (tuple, list)) and len(c) >= 2:
                        cookies_dict[str(c[0])] = str(c[1])
            if cookies_dict:
                save_cookies(cookies_dict)
                self.cookies = cookies_dict
        except Exception as exc:
            logger.warning(f"Failed to persist cookies: {exc}")


__all__ = ["CurlCFFIFetcher"]


