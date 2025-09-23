from __future__ import annotations

import re
import time
from typing import List, Set

import requests
from bs4 import BeautifulSoup
from googlesearch import search

from .headers import HeadersBuilder


IP_PORT_REGEX = re.compile(r"\b(?:(?:\d{1,3}\.){3}\d{1,3}):(\d{2,5})\b")


def _extract_proxies_from_html(html: str) -> Set[str]:
    proxies: Set[str] = set()
    for match in re.finditer(r"\b(?:(?:\d{1,3}\.){3}\d{1,3}):\d{2,5}\b", html):
        proxies.add(match.group(0))
    return proxies


def search_free_proxies(query: str = "free proxy list", max_results: int = 10, pause_sec: float = 2.0, timeout: float = 15.0) -> List[str]:
    """Search Google for free proxy lists and scrape IP:PORT entries.

    - Uses googlesearch to discover candidate pages
    - Fetches pages with randomized headers
    - Extracts IP:PORT via regex
    """
    headers_builder = HeadersBuilder()
    session = requests.Session()
    session.headers.update(headers_builder.build())

    queries = [
        query,
        "free https proxies",
        "site:raw.githubusercontent.com proxy list",
        "socks5 proxy list",
        "free proxy txt",
    ]

    found: Set[str] = set()
    seen_urls: Set[str] = set()

    for q in queries:
        try:
            for url in search(q, num_results=max_results, advanced=False, lang="ru"):
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                try:
                    resp = session.get(url, timeout=timeout)
                    if resp.status_code >= 400 or not resp.text:
                        continue
                    content_type = resp.headers.get("content-type", "").lower()
                    text = resp.text
                    if "text/html" in content_type:
                        soup = BeautifulSoup(text, "lxml")
                        text = soup.get_text("\n", strip=False)
                    proxies = _extract_proxies_from_html(text)
                    if proxies:
                        found.update(proxies)
                except Exception:
                    continue
                time.sleep(0.8)
        except Exception:
            # If search fails, continue with next query
            continue
        time.sleep(pause_sec)

    # Simple sanity filter: keep only ports in range 1..65535
    sane: List[str] = []
    for p in found:
        try:
            port = int(IP_PORT_REGEX.search(p).group(1))  # type: ignore[union-attr]
            if 1 <= port <= 65535:
                sane.append(p)
        except Exception:
            continue
    return sorted(set(sane))


__all__ = ["search_free_proxies"]



