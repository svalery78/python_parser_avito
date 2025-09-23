from __future__ import annotations

from typing import Iterable

from sqlalchemy import create_engine, text

from database.models import DB_URL


def _column_exists(rows: Iterable[tuple], name: str) -> bool:
    for row in rows:
        # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
        if len(row) >= 2 and str(row[1]).lower() == name.lower():
            return True
    return False


def ensure_listings_columns() -> None:
    """Add missing columns to listings table (SQLite) via ALTER TABLE if needed."""
    engine = create_engine(DB_URL, future=True)
    with engine.begin() as conn:
        rows = list(conn.execute(text("PRAGMA table_info(listings)")))
        if not rows:
            return
        add_sql = []
        if not _column_exists(rows, "bail"):
            add_sql.append("ALTER TABLE listings ADD COLUMN bail VARCHAR(128)")
        if not _column_exists(rows, "tax"):
            add_sql.append("ALTER TABLE listings ADD COLUMN tax VARCHAR(128)")
        if not _column_exists(rows, "services"):
            add_sql.append("ALTER TABLE listings ADD COLUMN services TEXT")
        if not _column_exists(rows, "address"):
            add_sql.append("ALTER TABLE listings ADD COLUMN address VARCHAR(512)")
        if not _column_exists(rows, "metro"):
            add_sql.append("ALTER TABLE listings ADD COLUMN metro VARCHAR(512)")
        if not _column_exists(rows, "description"):
            add_sql.append("ALTER TABLE listings ADD COLUMN description TEXT")
        if not _column_exists(rows, "images"):
            add_sql.append("ALTER TABLE listings ADD COLUMN images TEXT")
        for sql in add_sql:
            conn.execute(text(sql))


__all__ = ["ensure_listings_columns"]


