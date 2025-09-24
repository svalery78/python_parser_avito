from __future__ import annotations

import re
import json
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


class ListingProcessor:
    """Extract structured data from Avito listing pages (multiple listings from index page)."""

    def extract_listings(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """Extract multiple listings from Avito index page.
        
        Args:
            soup: Parsed HTML soup
            base_url: Base URL for resolving relative links
            
        Returns:
            List of dictionaries with extracted listing data
        """
        listings = []
        # Keep reference to whole-page soup for meta fallbacks
        self._page_soup = soup
        
        # Find all listing containers
        # Try different selectors for listing items
        listing_selectors = [
            'div[data-marker="item"]',
            '.iva-item-root-_lk9K',
            '.styles-module-theme-_IJ5n',
            '.iva-item-content-fRmzq',
        ]
        
        listing_containers = []
        for selector in listing_selectors:
            containers = soup.select(selector)
            if containers:
                listing_containers = containers
                break
        
        if not listing_containers:
            print("No listing containers found")
            return listings
        
        print(f"Found {len(listing_containers)} listing containers")
        # Store listing count for description fallback logic
        self._listing_count = len(listing_containers)
        
        for container in listing_containers:
            try:
                listing_data = self._extract_single_listing(container, base_url)
                if listing_data:
                    listings.append(listing_data)
            except Exception as e:
                print(f"Error extracting listing: {e}")
                continue
        
        return listings

    def _extract_single_listing(self, container, base_url: str) -> Optional[Dict[str, Any]]:
        """Extract data from a single listing container."""
        result = {}
        
        # Extract title
        title = self._extract_title_from_container(container)
        result['title'] = title
        
        # Extract price
        price = self._extract_price_from_container(container)
        result['price'] = price
        
        # Extract bail (залог)
        bail = self._extract_bail_from_container(container)
        result['bail'] = bail
        
        # Extract tax (комиссия)
        tax = self._extract_tax_from_container(container)
        result['tax'] = tax
        
        # Extract services (ЖКУ)
        services = self._extract_services_from_container(container)
        result['services'] = services
        
        # Extract address
        address = self._extract_address_from_container(container)
        result['address'] = address
        
        # Extract description
        desc = self._extract_description_from_container(container)
        result['desc'] = desc
        
        # Extract images
        images = self._extract_images_from_container(container, base_url)
        result['images'] = images
        
        # Extract link
        link = self._extract_link_from_container(container, base_url)
        result['link'] = link
        
        # Only return if we have at least title or price
        if title or price:
            return result
        
        return None

    def _extract_title_from_container(self, container) -> Optional[str]:
        """Extract title from listing container."""
        selectors = [
            '[data-marker="item-title"]',
            '.iva-item-titleStep-_dJLR',
            '.iva-item-titleStep-_dJLR a',
            'h3 a',
            'h3',
            '.title-root-zZCwT',
        ]
        
        for selector in selectors:
            element = container.select_one(selector)
            if element:
                # Get text from link or element
                link = element.find('a')
                if link:
                    text = link.get_text(strip=True)
                else:
                    text = element.get_text(strip=True)
                
                if text and len(text) > 5:  # Filter out very short titles
                    return text
        
        return None

    def _extract_price_from_container(self, container) -> Optional[str]:
        """Extract price from listing container."""
        selectors = [
            '[data-marker="item-price"]',
            '.iva-item-priceStep-_qC3a',
            '.price-text-_YGDY',
            '.price-root-_y9Jn',
        ]
        
        for selector in selectors:
            element = container.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                if price_text and ('₽' in price_text or 'руб' in price_text.lower()):
                    return price_text
        
        # Fallback: search for price patterns in text
        text_content = container.get_text()
        price_patterns = [
            r'(\d+[\s\d]*\s*₽[^.\n]*)',
            r'(\d+[\s\d]*\s*руб[^.\n]*)',
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text_content)
            if match:
                return match.group(1).strip()
        
        return None

    def _extract_bail_from_container(self, container) -> Optional[str]:
        """Extract bail information from container."""
        text_content = container.get_text()
        bail_patterns = [
            r'Залог[:\s]*([^.\n]+)',
            r'залог[:\s]*([^.\n]+)',
        ]
        
        for pattern in bail_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return f"Залог {match.group(1).strip()}"
        
        return None

    def _extract_tax_from_container(self, container) -> Optional[str]:
        """Extract tax/commission information from container."""
        text_content = container.get_text()
        tax_patterns = [
            r'Без комиссии',
            r'Комиссия[:\s]*([^.\n]+)',
            r'комиссия[:\s]*([^.\n]+)',
        ]
        
        for pattern in tax_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                if 'без комиссии' in match.group(0).lower():
                    return "Без комиссии"
                return match.group(0).strip()
        
        return None

    def _extract_services_from_container(self, container) -> Optional[str]:
        """Extract services/utilities information from container."""
        text_content = container.get_text()
        services_patterns = [
            r'ЖКУ[:\s]*([^.\n]+)',
            r'жкх[:\s]*([^.\n]+)',
            r'коммуналка[:\s]*([^.\n]+)',
        ]
        
        for pattern in services_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return f"ЖКУ {match.group(1).strip()}"
        
        return None

    def _extract_address_from_container(self, container) -> Optional[str]:
        """Extract address information from container."""
        selectors = [
            '[data-marker="item-address"]',
            '.geo-root-_K_ZR',
            '.geo-address-_9qJw',
            '.address-root-_XwNP',
        ]
        
        for selector in selectors:
            element = container.select_one(selector)
            if element:
                address_text = element.get_text(strip=True)
                if address_text and len(address_text) > 3:
                    return address_text
        
        # Fallback: search for address-like patterns
        text_content = container.get_text()
        address_patterns = [
            r'([А-Яа-яё\s]+(?:ул\.|улица|проспект|пр\.|переулок|пер\.)[^.\n]*)',
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, text_content)
            if match:
                return match.group(1).strip()
        
        return None

    def _extract_description_from_container(self, container) -> Optional[str]:
        """Extract description from container."""
        # 1) Prefer container-level meta descriptions (unique per item on index page)
        meta_in_container = (
            container.select_one('meta[itemprop="description"]')
            or container.select_one('meta[name="description"]')
            or container.select_one('meta[property="og:description"]')
        )
        if meta_in_container and meta_in_container.get("content"):
            meta_text = meta_in_container.get("content", "").strip()
            if meta_text:
                return re.sub(r'\s+', ' ', meta_text)

        # 2) Try visible description blocks inside the container
        selectors = [
            '[data-marker="item-description"]',
            '.iva-item-text-_s_vH',
            '.item-description-text',
        ]
        
        for selector in selectors:
            element = container.select_one(selector)
            if element:
                desc_text = element.get_text(strip=True)
                if desc_text and len(desc_text) > 10:
                    # Clean up excessive whitespace
                    desc_text = re.sub(r'\s+', ' ', desc_text)
                    return desc_text
        # 3) Fallback to page-level meta ONLY if this is a detail page (single listing)
        try:
            if getattr(self, "_listing_count", None) == 1:
                page_soup = getattr(self, "_page_soup", None)
                if page_soup is not None:
                    meta = page_soup.select_one('meta[itemprop="description"]') or page_soup.select_one('meta[name="description"]')
                    if meta and meta.get("content"):
                        meta_text = meta.get("content", "").strip()
                        if meta_text:
                            meta_text = re.sub(r'\s+', ' ', meta_text)
                            return meta_text
        except Exception:
            pass

        return None

    def _extract_images_from_container(self, container, base_url: str) -> List[str]:
        """Extract first 3 image URLs from the carousel in the listing container."""
        images: List[str] = []

        # Primary: read from carousel list items, which often encode full URL in data-marker
        # Example: li[data-marker="slider-image/image-https://..."] > div > img
        li_nodes = container.select('ul.photo-slider-list-R0jle li.photo-slider-list-item-r2YDC')
        for li in li_nodes:
            if len(images) >= 3:
                break
            data_marker = li.get('data-marker') or ''
            if data_marker.startswith('slider-image/image-'):
                url = data_marker.replace('slider-image/image-', '', 1).strip()
                if url.startswith('//'):
                    url = 'https:' + url
                elif url.startswith('/'):
                    url = urljoin(base_url, url)
                if url and url not in images:
                    images.append(url)
                    continue
            # Fallback to the img src inside this li
            img = li.select_one('img')
            if img:
                src = img.get('src') or img.get('data-src') or ''
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = urljoin(base_url, src)
                    if any(size in src for size in ['16x16', '24x24', '32x32']) or 'icon' in src.lower():
                        continue
                    if src not in images:
                        images.append(src)

        # Secondary: if still fewer than 3, broaden search within the container
        if len(images) < 3:
            extras = []
            for img in container.select('img'):
                src = img.get('src') or img.get('data-src') or ''
                if not src:
                    continue
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(base_url, src)
                if not src.startswith('http'):
                    continue
                if any(size in src for size in ['16x16', '24x24', '32x32']) or 'icon' in src.lower():
                    continue
                extras.append(src)
            for src in extras:
                if len(images) >= 3:
                    break
                if src not in images:
                    images.append(src)

        return images[:3]

    def _extract_link_from_container(self, container, base_url: str) -> Optional[str]:
        """Extract listing link from container."""
        # Try different selectors for links
        link_selectors = [
            'a[data-marker="item-title"]',
            '.iva-item-titleStep-_dJLR a',
            'h3 a',
            'a[href*="/kvartiry/"]',
            'a[href*="/moskva/"]',
        ]
        
        for selector in link_selectors:
            link_element = container.select_one(selector)
            if link_element:
                href = link_element.get('href')
                if href:
                    # Convert relative URLs to absolute
                    if href.startswith('//'):
                        return 'https:' + href
                    elif href.startswith('/'):
                        return urljoin(base_url, href)
                    elif href.startswith('http'):
                        return href
        
        return None


__all__ = ["ListingProcessor"]
