from __future__ import annotations

from typing import Optional
from pathlib import Path

from bs4 import BeautifulSoup

from services.curl_fetcher import CurlCFFIFetcher
from services.playwright_fetcher import PlaywrightFetcher
from services.output_dispatcher import OutputDispatcher
from services.processor import ListingProcessor
from utils.headers import HeadersBuilder
from utils.proxy_finder import search_free_proxies
from database.sqlite import save_multiple_listings


class Parser:
    """High-level parser orchestrating network fetchers and output dispatching."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        use_playwright: bool = False,
        dispatcher: Optional[OutputDispatcher] = None,
    ) -> None:
        self.dispatcher = dispatcher or OutputDispatcher()
        self.headers_builder = HeadersBuilder()
        self.curl = CurlCFFIFetcher(base_url=base_url, headers_builder=self.headers_builder)
        self.pw = PlaywrightFetcher(headless=True, base_url=base_url)
        self.use_pw = use_playwright

    def fetch(self, path_or_url: str) -> str:
        if self.use_pw:
            import asyncio

            return asyncio.run(self.pw.get(path_or_url))
        try:
            return self.curl.get(path_or_url)
        except Exception:
            # Fallback to Playwright when HTTP client fails (e.g., 403/429/protection)
            import asyncio
            try:
                return asyncio.run(self.pw.get(path_or_url))
            except Exception:
                # Try a few free proxies as a last resort
                proxies = search_free_proxies(max_results=5)
                for p in proxies[:5]:
                    proxy_url = f"http://{p}"
                    try:
                        return self.curl.get(path_or_url, proxy_url=proxy_url)
                    except Exception:
                        continue
                raise

    def parse_and_output(self, path_or_url: str) -> None:
        html = self.fetch(path_or_url)
        # Save raw HTML to trash for temporary inspection
        base_dir = Path(__file__).resolve().parents[1]
        trash_dir = base_dir / 'trash'
        trash_dir.mkdir(parents=True, exist_ok=True)
        safe_name = 'page.html'
        try:
            from urllib.parse import quote

            safe_name = quote(path_or_url, safe='')[:120] + '.html'
        except Exception:
            pass
        (trash_dir / safe_name).write_text(html, encoding='utf-8', errors='ignore')
        soup = BeautifulSoup(html, "lxml")
        
        # Try to extract multiple listings from the page
        processor = ListingProcessor()
        # Extract base URL from the full URL
        from urllib.parse import urlparse
        parsed_url = urlparse(path_or_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        listings = processor.extract_listings(soup=soup, base_url=base_url)
        
        if listings:
            # Save all extracted listings to database
            saved_count = save_multiple_listings(listings)
            self.dispatcher.dispatch(f"Saved {saved_count} listings from {len(listings)} found")
            
            # Print summary of saved listings
            for i, listing in enumerate(listings[:3]):  # Show first 3
                title = listing.get('title', 'No title')[:50]
                price = listing.get('price', 'No price')[:30]
                self.dispatcher.dispatch(f"  {i+1}. {title} - {price}")
            
            if len(listings) > 3:
                self.dispatcher.dispatch(f"  ... and {len(listings) - 3} more")
        else:
            # fallback: dump raw text
            text_content = soup.get_text("\n", strip=True)
            self.dispatcher.dispatch(text_content)


__all__ = ["Parser"]


