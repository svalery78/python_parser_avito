from __future__ import annotations

from pathlib import Path
from typing import Tuple

from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.models import Base, Listing, DB_URL


def init_db() -> None:
    engine = create_engine(DB_URL, future=True)
    Base.metadata.create_all(engine)


def parse_and_insert(html_path: Path) -> Tuple[int, list[dict]]:
    engine = create_engine(DB_URL, future=True)
    Base.metadata.create_all(engine)

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "lxml")
    inserted = 0
    examples: list[dict] = []

    # Avito listing cards often have data-marker="item" or similar structure
    # Fallback: parse generic anchors that look like ads
    cards = soup.select('[data-marker="item"]')
    if not cards:
        cards = soup.select("a[href*='/moskva/']")  # heuristic fallback

    with Session(engine) as session:
        for card in cards:
            try:
                a = card if card.name == "a" else card.find("a", href=True)
                if not a or not a.get("href"):
                    continue
                href = a.get("href")
                url = href if href.startswith("http") else f"https://www.avito.ru{href}"

                title_el = card.select_one('[itemprop="name"], h3, h2') or a
                title = title_el.get_text(strip=True) if title_el else None

                price_el = card.select_one('[data-marker="item-price"], [itemprop="price"], .price')
                price = price_el.get_text(strip=True) if price_el else None

                loc_el = card.select_one('[data-marker="item-location"], .geo-root, .geo-address')
                location = loc_el.get_text(strip=True) if loc_el else None

                snippet = card.get_text(" ", strip=True)[:500]

                # Upsert by URL
                exists = session.execute(select(Listing).where(Listing.url == url)).scalar_one_or_none()
                if exists:
                    continue
                obj = Listing(url=url, title=title, price=price, location=location, snippet=snippet)
                session.add(obj)
                session.flush()
                inserted += 1
                if len(examples) < 3:
                    examples.append({
                        "url": url,
                        "title": title,
                        "price": price,
                        "location": location,
                    })
            except Exception as e:
                logger.debug(f"skip card: {e}")

        session.commit()

    return inserted, examples


__all__ = ["init_db", "parse_and_insert"]


