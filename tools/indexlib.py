"""Shared helpers for the index tools: paths, version ordering, file hashing."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.json"
MANIFESTS = ROOT / "manifests"
SCHEMA = ROOT / "schema" / "manifest.schema.json"
INDEX_SCHEMA_VERSION = "1"


def version_key(v: str) -> tuple:
    """Numeric parts compare as numbers (0.10.0 > 0.9.0); same rule as the catalog."""
    parts = re.findall(r"\d+|[A-Za-z]+", v.lstrip("v"))
    return tuple((0, int(p)) if p.isdigit() else (-1, p) for p in parts)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_path(app_id: str, version: str) -> Path:
    return MANIFESTS / app_id / f"{version}.json"


def load_index() -> dict:
    if not INDEX.exists():
        return {"schema_version": INDEX_SCHEMA_VERSION, "name": "", "updated": "", "extensions": []}
    return json.loads(INDEX.read_text())


def save_index(index: dict) -> None:
    INDEX.write_text(json.dumps(index, indent=2) + "\n")
