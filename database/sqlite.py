from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Dict, Any

from sqlalchemy import Column, Integer, String, Text, DateTime, create_engine, select, and_
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_DIR / "avito_listings.db"

Base = declarative_base()


class Page(Base):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(1000), index=True, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=True)
    price = Column(String(200), nullable=True)
    bail = Column(String(200), nullable=True)
    tax = Column(String(200), nullable=True)
    services = Column(String(500), nullable=True)
    address = Column(String(1000), nullable=True)
    desc = Column(Text, nullable=True)
    images = Column(Text, nullable=True)  # store as JSON string
    link = Column(String(2000), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _make_engine():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_database_initialized() -> None:
    Base.metadata.create_all(engine)


class SQLiteOutputHandler:
    def send(self, payload: str, *, meta: Optional[Dict[str, Any]] = None) -> None:
        url = None
        if meta and isinstance(meta.get("url"), str):
            url = meta["url"]
        if not url:
            url = ""
        with SessionLocal() as session:
            session.add(Page(url=url, content=payload))
            session.commit()


def save_listing(*, title: str | None, price: str | None, bail: str | None, tax: str | None,
                 services: str | None, address: str | None, desc: str | None,
                 images: list[str] | None, link: str) -> None:
    """Save extracted listing data to database."""
    import json
    ensure_database_initialized()
    images_json = json.dumps(images or [], ensure_ascii=False)
    with SessionLocal() as session:
        session.add(
            Listing(
                title=title,
                price=price,
                bail=bail,
                tax=tax,
                services=services,
                address=address,
                desc=desc,
                images=images_json,
                link=link,
            )
        )
        session.commit()


def save_multiple_listings(listings: list[dict]) -> int:
    """Save multiple listings to database.
    
    Args:
        listings: List of dictionaries with listing data
        
    Returns:
        Number of listings saved
    """
    import json
    ensure_database_initialized()
    
    saved_count = 0
    with SessionLocal() as session:
        for listing in listings:
            try:
                images_json = json.dumps(listing.get('images') or [], ensure_ascii=False)
                # Deduplicate by all columns except images (title, price, bail, tax, services, address, desc, link)
                stmt = select(Listing.id).where(and_(
                    Listing.title == listing.get('title'),
                    Listing.price == listing.get('price'),
                    Listing.bail == listing.get('bail'),
                    Listing.tax == listing.get('tax'),
                    Listing.services == listing.get('services'),
                    Listing.address == listing.get('address'),
                    Listing.desc == listing.get('desc'),
                    Listing.link == listing.get('link', ''),
                ))
                exists = session.execute(stmt).first()
                if exists:
                    continue

                session.add(Listing(
                    title=listing.get('title'),
                    price=listing.get('price'),
                    bail=listing.get('bail'),
                    tax=listing.get('tax'),
                    services=listing.get('services'),
                    address=listing.get('address'),
                    desc=listing.get('desc'),
                    images=images_json,
                    link=listing.get('link', ''),
                ))
                saved_count += 1
            except Exception as e:
                print(f"Error saving listing: {e}")
                continue
        
        session.commit()
    
    return saved_count


__all__ = [
    "Base",
    "SessionLocal",
    "ensure_database_initialized",
    "SQLiteOutputHandler",
    "Listing",
    "save_listing",
    "save_multiple_listings",
]
