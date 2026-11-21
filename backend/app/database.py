from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from app.config import get_database_path
from app.models import ListingContent, ProductData


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(get_database_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with _connect() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS listings (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                source_url TEXT NOT NULL,
                product_json TEXT NOT NULL,
                content_json TEXT NOT NULL,
                html TEXT NOT NULL,
                thumbnail_url TEXT NOT NULL DEFAULT ''
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS openai_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                input_price_per_million REAL,
                output_price_per_million REAL,
                estimated_cost_usd REAL
            )"""
        )


def get_preference(key: str, default: str = "") -> str:
    with _connect() as connection:
        row = connection.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_preference(key: str, value: str) -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT INTO preferences(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def record_openai_usage(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    input_price_per_million: float | None,
    output_price_per_million: float | None,
) -> None:
    estimated_cost = None
    if input_price_per_million is not None and output_price_per_million is not None:
        estimated_cost = round(
            (input_tokens * input_price_per_million + output_tokens * output_price_per_million) / 1_000_000,
            12,
        )
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as connection:
        connection.execute(
            """INSERT INTO openai_usage
            (created_at, model, input_tokens, output_tokens, total_tokens,
             input_price_per_million, output_price_per_million, estimated_cost_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                created_at,
                model,
                input_tokens,
                output_tokens,
                total_tokens,
                input_price_per_million,
                output_price_per_million,
                estimated_cost,
            ),
        )


def get_openai_usage_summary() -> dict[str, int | float]:
    with _connect() as connection:
        row = connection.execute(
            """SELECT COUNT(*) AS request_count,
                      COALESCE(SUM(input_tokens), 0) AS input_tokens,
                      COALESCE(SUM(output_tokens), 0) AS output_tokens,
                      COALESCE(SUM(total_tokens), 0) AS total_tokens,
                      COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd,
                      COALESCE(SUM(CASE WHEN estimated_cost_usd IS NULL THEN 1 ELSE 0 END), 0)
                          AS unpriced_request_count
               FROM openai_usage"""
        ).fetchone()
    return {
        "request_count": int(row["request_count"]),
        "input_tokens": int(row["input_tokens"]),
        "output_tokens": int(row["output_tokens"]),
        "total_tokens": int(row["total_tokens"]),
        "estimated_cost_usd": round(float(row["estimated_cost_usd"]), 12),
        "unpriced_request_count": int(row["unpriced_request_count"]),
    }


def save_listing(product: ProductData, content: ListingContent, html: str) -> dict[str, Any]:
    listing_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    thumbnail = next((image.url for image in product.images if image.selected), "")
    with _connect() as connection:
        connection.execute(
            """INSERT INTO listings
            (id, title, created_at, source_url, product_json, content_json, html, thumbnail_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                listing_id,
                content.title,
                created_at,
                product.source_url,
                product.model_dump_json(),
                content.model_dump_json(),
                html,
                thumbnail,
            ),
        )
    return {
        "id": listing_id,
        "title": content.title,
        "created_at": created_at,
        "source_url": product.source_url,
        "thumbnail_url": thumbnail,
    }


def list_listings(limit: int = 100) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, title, created_at, source_url, thumbnail_url FROM listings "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_listing(listing_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "source_url": row["source_url"],
        "thumbnail_url": row["thumbnail_url"],
        "product": json.loads(row["product_json"]),
        "content": json.loads(row["content_json"]),
        "html": row["html"],
    }
