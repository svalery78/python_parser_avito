from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import String, Integer, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "avito_listings.db"
DB_URL = f"sqlite:///{DB_PATH}"


class Base(DeclarativeBase):
    pass


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("url", name="uq_listings_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=True)
    price: Mapped[str] = mapped_column(String(64), nullable=True)
    location: Mapped[str] = mapped_column(String(256), nullable=True)
    snippet: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


__all__ = [
    "Base",
    "Listing",
    "DB_URL",
]


