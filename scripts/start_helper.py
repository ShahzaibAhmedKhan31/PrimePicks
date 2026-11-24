"""Small checks used by start.cmd, which has no built-in hashing or timestamp comparison.

    python scripts/start_helper.py changed <file> <marker>   exit 10 if <file> changed since `mark`
    python scripts/start_helper.py mark <file> <marker>      record the current hash of <file>
    python scripts/start_helper.py ui-stale                  exit 10 if the interface needs rebuilding

The marker format (sha256 hex plus a newline) matches start.sh, so both launchers share setup.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_SOURCES = ("src", "index.html", "vite.config.js", "package.json")
NEEDS_UPDATE = 10


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed(path: Path, marker: Path) -> int:
    try:
        recorded = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return NEEDS_UPDATE
    return 0 if recorded == file_hash(path) else NEEDS_UPDATE


def mark(path: Path, marker: Path) -> int:
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(file_hash(path) + "\n", encoding="utf-8", newline="\n")
    return 0


def ui_stale() -> int:
    built = ROOT / "frontend_dist" / "index.html"
    if not built.is_file():
        return NEEDS_UPDATE
    built_at = built.stat().st_mtime
    for name in UI_SOURCES:
        source = ROOT / name
        paths = source.rglob("*") if source.is_dir() else [source]
        if any(p.is_file() and p.stat().st_mtime > built_at for p in paths):
            return NEEDS_UPDATE
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 1 and argv[0] == "ui-stale":
        return ui_stale()
    if len(argv) == 3 and argv[0] in ("changed", "mark"):
        action = changed if argv[0] == "changed" else mark
        return action(Path(argv[1]), Path(argv[2]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
