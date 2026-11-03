#!/usr/bin/env python3
"""Validate the index: what CI runs on every PR and push.

    tools/validate.py [--base <git-ref>]

Checks
  - index.json shape; ids unique; versions unique and newest-first; latest = highest version
  - categories: ids unique and non-empty, labels non-empty; every extension's category is listed
  - every extension's support is platform9, partner or community
  - every listed manifest exists, its sha256 matches, its id/version match the entry and the path
  - every manifest validates against schema/manifest.schema.json (structure; the catalog's
    pydantic validator adds semantic rules and runs before submission and on load)
  - a manifest's icon is a relative .svg path inside its repo (no leading "/", no "..")
  - no manifest file is left out of the index
  - with --base: no manifest that exists at <git-ref> has changed or been deleted. While
    indexlib.MANIFESTS_LOCKED is False (schema in development) such changes are listed as notes
    and don't fail; once it is True, published versions are immutable.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from indexlib import INDEX, INDEX_SCHEMA_VERSION, MANIFESTS, MANIFESTS_LOCKED, ROOT, SCHEMA, SUPPORT_LEVELS, load_index, sha256_file, version_key  # noqa: E402

try:
    import jsonschema
except ImportError:  # pragma: no cover
    sys.exit("pip install jsonschema")


def check(base: str | None) -> tuple[list[str], list[str]]:
    """(errors, notes)."""
    errors: list[str] = []
    if not INDEX.exists():
        return ["index.json is missing"], []
    index = load_index()
    if index.get("schema_version") != INDEX_SCHEMA_VERSION:
        errors.append(f"index.json schema_version must be {INDEX_SCHEMA_VERSION!r}")
    validator = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text()))
    listed: set[Path] = set()
    cat_ids = [c.get("id") for c in index.get("categories") or []]
    if not cat_ids:
        errors.append("index.json has no categories")
    for c in index.get("categories") or []:
        if not c.get("id"):
            errors.append(f"category {c!r} has no id")
        elif not c.get("label"):
            errors.append(f"category {c['id']!r} has no label")
    for dup in {i for i in cat_ids if cat_ids.count(i) > 1}:
        errors.append(f"category {dup!r} is listed more than once")
    ids = [e.get("id") for e in index.get("extensions", [])]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"extension {dup!r} is listed more than once")
    for entry in index.get("extensions", []):
        app_id = entry.get("id", "?")
        if entry.get("category") not in cat_ids:
            errors.append(f"{app_id}: category {entry.get('category')!r} is not in index.json categories")
        if entry.get("support") not in SUPPORT_LEVELS:
            errors.append(f"{app_id}: support {entry.get('support')!r} must be one of {', '.join(SUPPORT_LEVELS)}")
        versions = entry.get("versions") or []
        if not versions:
            errors.append(f"{app_id}: no versions")
            continue
        names = [v.get("version") for v in versions]
        if len(names) != len(set(names)):
            errors.append(f"{app_id}: duplicate versions")
        if names != sorted(names, key=version_key, reverse=True):
            errors.append(f"{app_id}: versions must be newest first")
        if entry.get("latest") != max(names, key=version_key):
            errors.append(f"{app_id}: latest is {entry.get('latest')!r}, highest version is {max(names, key=version_key)!r}")
        for v in versions:
            rel = v.get("manifest", "")
            path = (ROOT / rel).resolve()
            expected = MANIFESTS / app_id / f"{v.get('version')}.json"
            if path != expected.resolve():
                errors.append(f"{app_id} {v.get('version')}: manifest path must be {expected.relative_to(ROOT)}")
            if not path.is_file():
                errors.append(f"{app_id} {v.get('version')}: {rel} not found")
                continue
            listed.add(path)
            if sha256_file(path) != v.get("sha256"):
                errors.append(f"{app_id} {v.get('version')}: sha256 does not match {rel}")
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError as e:
                errors.append(f"{rel}: invalid JSON: {e}")
                continue
            if (data.get("id"), data.get("version")) != (app_id, v.get("version")):
                errors.append(f"{rel}: id/version {data.get('id')}/{data.get('version')} don't match the index entry")
            icon = data.get("icon")
            if icon is not None and (not isinstance(icon, str) or icon.startswith("/")
                                     or ".." in icon.split("/") or not icon.endswith(".svg")):
                errors.append(f"{rel}: icon {icon!r} must be a relative .svg path inside the repo")
            for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
                loc = ".".join(str(p) for p in err.path) or "(manifest)"
                errors.append(f"{rel}: {loc}: {err.message}")
    for path in sorted(MANIFESTS.glob("*/*.json")):
        if path.resolve() not in listed:
            errors.append(f"{path.relative_to(ROOT)} is not listed in index.json")
    notes: list[str] = []
    if base:
        (errors if MANIFESTS_LOCKED else notes).extend(immutability(base))
    return errors, notes


def immutability(base: str) -> list[str]:
    """Published manifests (present at `base`) must be byte-identical now."""
    out = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", base, "manifests/"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return [f"can't read git ref {base!r}: {out.stderr.strip()}"]
    errors = []
    for rel in out.stdout.split():
        old = subprocess.run(["git", "-C", str(ROOT), "show", f"{base}:{rel}"], capture_output=True).stdout
        new = ROOT / rel
        if not new.exists():
            errors.append(f"{rel}: published manifest was deleted")
        elif new.read_bytes() != old:
            errors.append(f"{rel}: published manifest was changed"
                          + ("; publish a new version instead" if MANIFESTS_LOCKED else ""))
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate the extension index")
    ap.add_argument("--base", help="git ref whose manifests must be unchanged (e.g. origin/main)")
    errors, notes = check(ap.parse_args().base)
    for n in notes:
        print(f"note: {n} (allowed: manifests are unlocked)")
    for e in errors:
        print(f"error: {e}")
    print("index OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
