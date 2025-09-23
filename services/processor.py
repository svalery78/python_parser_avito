from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Iterable

from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.models import DB_URL, Base, Listing
from services.db_utils import ensure_listings_columns


IMG_RE = re.compile(r"https?://[\w\-\./%?=&#:+]+\.(?:jpg|jpeg|png|webp)(?:[\w\-\./%?=&#:+]+)?", re.I)


def _text(el) -> Optional[str]:
    return el.get_text(strip=True) if el else None


def _find_first_images(soup: BeautifulSoup, limit: int = 3) -> List[str]:
    urls: List[str] = []
    # Prefer gallery images
    for img in soup.select('img[src]'):
        src = img.get('src') or ''
        if IMG_RE.search(src):
            urls.append(src)
        if len(urls) >= limit:
            break
    return urls


def parse_detail_html(html_text: str) -> Dict[str, Optional[str]]:
    soup = BeautifulSoup(html_text, 'lxml')
    # Title
    title = _text(soup.select_one('[data-marker="item-view/title-info"] h1, h1'))
    if not title:
        title = _text(soup.select_one('[itemprop="name"], .title-info-title-text'))
    # Price
    price = _text(soup.select_one('[data-marker="item-price"], [itemprop="price"], .price-value-string, .style-item-price__string'))
    # Bail / deposit
    bail = None
    for el in soup.find_all(text=re.compile(r"зал(о|о)г", re.I)):
        seg = el.parent.get_text(" ", strip=True)
        m = re.search(r"залог\s*([\d\s]+\s*₽)", seg, re.I)
        if m:
            bail = f"залог {m.group(1).strip()}"
            break
    # Tax / commission
    tax = None
    for el in soup.find_all(text=re.compile(r"комисси", re.I)):
        seg = el.parent.get_text(" ", strip=True)
        m = re.search(r"комисси[ия]\s*([\d\s]+\s*%|нет)", seg, re.I)
        if m:
            tax = f"комиссия {m.group(1).strip()}"
            break
    # Services block
    services = None
    sv_el = soup.find(text=re.compile(r"ЖКУ|счётчик|счетчик|оплачивается отдельно|включен", re.I))
    if sv_el:
        services = sv_el.parent.get_text(" ", strip=True)
    # Address
    address = _text(soup.select_one('[data-marker="delivery/location"] [itemprop="address"], [itemprop="address"], .style-item-address__string'))
    # Metro
    metro_el = soup.find(text=re.compile(r"мин\.?|метро", re.I))
    metro = metro_el.parent.get_text(" ", strip=True) if metro_el else None
    # Description
    desc = _text(soup.select_one('[data-marker="item-view/description"], [itemprop="description"], .style-item-description'))
    # Images
    images = _find_first_images(soup, limit=3)

    return {
        'title': title,
        'price': price,
        'bail': bail,
        'tax': tax,
        'services': services,
        'address': address,
        'metro': metro,
        'desc': desc,
        'images': images,
    }


def save_detail_to_db(url: str, data: Dict[str, Optional[str]]) -> None:
    engine = create_engine(DB_URL, future=True)
    Base.metadata.create_all(engine)
    ensure_listings_columns()
    with Session(engine) as session:
        exists = session.execute(select(Listing).where(Listing.url == url)).scalar_one_or_none()
        if exists:
            # Update fields if empty
            for fld, key in (
                ('title', 'title'), ('price', 'price'), ('snippet', 'desc'),
            ):
                val = data.get(key)
                if val and not getattr(exists, fld, None):
                    setattr(exists, fld, val)
            # New columns via ALTER TABLE are set by raw SQL in ensure_listings_columns
            try:
                for fld in ('bail','tax','services','address','metro','description','images'):
                    if fld == 'description':
                        v = data.get('desc')
                    elif fld == 'images':
                        v = json.dumps(data.get('images') or [])
                    else:
                        v = data.get(fld)
                    if v:
                        setattr(exists, fld, v)
            except Exception:
                pass
        else:
            from sqlalchemy import insert
            payload = {
                'url': url,
                'title': data.get('title'),
                'price': data.get('price'),
                'snippet': data.get('desc'),
            }
            session.execute(insert(Listing).values(**payload))
        session.commit()


__all__ = [
    'parse_detail_html',
    'save_detail_to_db',
]


def _extract_bail_tax(text_block: str) -> (Optional[str], Optional[str]):
    bail = None
    tax = None
    m = re.search(r"залог\s*([\d\s]+\s*₽)", text_block, re.I)
    if m:
        bail = f"залог {m.group(1).strip()}"
    m = re.search(r"комисси[ия]\s*([\d\s]+\s*%|нет)", text_block, re.I)
    if m:
        val = m.group(1).strip()
        if not val.endswith('%') and val.lower() != 'нет':
            val += ' %'
        tax = f"комиссия {val}"
    return bail, tax


def parse_list_html(html_text: str) -> List[Dict[str, Optional[str]]]:
    """Parse Avito search result list page into structured items."""
    soup = BeautifulSoup(html_text, 'lxml')
    items: List[Dict[str, Optional[str]]] = []

    # Each card
    cards = soup.select('[data-marker="item"]')
    for card in cards:
        try:
            # URL and title
            a = card.select_one('[data-marker="item-title"] a[href], a[href]')
            href = a.get('href') if a else None
            url = href if href and href.startswith('http') else (f"https://www.avito.ru{href}" if href else None)
            title_el = card.select_one('[data-marker="item-title"], h3, h2')
            title = _text(title_el)

            # Price
            price = _text(card.select_one('[data-marker="item-price"], .price-root-RA1pj'))

            # Bail & tax from auto params block
            params_el = card.select_one('div.iva-item-autoParamsStep-A7hVP.iva-item-ivaItemRedesign-QmNXd')
            bail = tax = None
            if params_el:
                bail, tax = _extract_bail_tax(params_el.get_text(' ', strip=True))

            # Address (with metro info)
            addr_el = card.select_one('div.iva-item-ivaItemRedesign-QmNXd[data-marker="item-address"]')
            address = _text(addr_el)

            # Description bottom block
            desc_el = card.select_one('div.iva-item-bottomBlock-VewGa')
            desc = _text(desc_el)

            # Images (first 3)
            images: List[str] = []
            for img in card.select('div[data-marker="item-photo"] img[src]'):
                src = img.get('src')
                if src and IMG_RE.search(src):
                    images.append(src)
                if len(images) >= 3:
                    break

            items.append({
                'url': url,
                'title': title,
                'price': price,
                'bail': bail,
                'tax': tax,
                'address': address,
                'metro': None,  # metro often embedded into address text
                'desc': desc,
                'images': images,
            })
        except Exception as e:
            logger.debug(f'parse card error: {e}')
            continue

    return items


def save_list_to_db(items: Iterable[Dict[str, Optional[str]]]) -> int:
    engine = create_engine(DB_URL, future=True)
    Base.metadata.create_all(engine)
    ensure_listings_columns()
    inserted = 0
    with Session(engine) as session:
        from sqlalchemy import insert
        for it in items:
            url = it.get('url') or ''
            if not url:
                continue
            exists = session.execute(select(Listing).where(Listing.url == url)).scalar_one_or_none()
            if exists:
                # Update selected fields
                for fld, key in (
                    ('title','title'), ('price','price'), ('snippet','desc'),
                ):
                    v = it.get(key)
                    if v and not getattr(exists, fld, None):
                        setattr(exists, fld, v)
                try:
                    for fld in ('bail','tax','services','address','metro','description','images'):
                        if fld == 'description':
                            v = it.get('desc')
                        elif fld == 'images':
                            v = json.dumps(it.get('images') or [])
                        else:
                            v = it.get(fld)
                        if v:
                            setattr(exists, fld, v)
                except Exception:
                    pass
            else:
                payload = {
                    'url': url,
                    'title': it.get('title'),
                    'price': it.get('price'),
                    'snippet': it.get('desc'),
                }
                session.execute(insert(Listing).values(**payload))
                inserted += 1
        session.commit()
    return inserted



