from __future__ import annotations

import os
import sys
from pathlib import Path

from platformdirs import user_data_dir

if not getattr(sys, "frozen", False):
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except ImportError:
        pass

APP_NAME = "PrimePick Goods Listing Generator"
APP_VENDOR = "PrimePick Goods"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def get_data_dir() -> Path:
    """Return a persistent per-user directory (never the install directory)."""
    override = os.getenv("PRIMEPICK_DATA_DIR")
    path = Path(override).expanduser() if override else Path(user_data_dir(APP_NAME, APP_VENDOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_template_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "app" / "templates"
    return Path(__file__).resolve().parent / "templates"


def get_frontend_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "frontend_dist"
    return Path(__file__).resolve().parents[2] / "frontend_dist"


def get_database_path() -> Path:
    return get_data_dir() / "primepick-goods.sqlite3"
