#!/usr/bin/env python3
"""Validate the index: what CI runs on every PR and push.

    tools/validate.py [--base <git-ref>]

Checks
  - index.json shape; ids unique; versions unique and newest-first; latest = highest version
  - every listed manifest exists, its sha256 matches, its id/version match the entry and the path
  - every manifest validates against schema/manifest.schema.json (structure; the catalog's
    pydantic validator adds semantic rules and runs before submission and on load)
  - no manifest file is left out of the index
  - with --base: no manifest that exists at <git-ref> has changed (published versions are immutable)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from indexlib import INDEX, INDEX_SCHEMA_VERSION, MANIFESTS, ROOT, SCHEMA, load_index, sha256_file, version_key  # noqa: E402

try:
    import jsonschema
except ImportError:  # pragma: no cover
    sys.exit("pip install jsonschema")


def check(base: str | None) -> list[str]:
    errors: list[str] = []
    if not INDEX.exists():
        return ["index.json is missing"]
    index = load_index()
    if index.get("schema_version") != INDEX_SCHEMA_VERSION:
        errors.append(f"index.json schema_version must be {INDEX_SCHEMA_VERSION!r}")
    validator = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text()))
    listed: set[Path] = set()
    ids = [e.get("id") for e in index.get("extensions", [])]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"extension {dup!r} is listed more than once")
    for entry in index.get("extensions", []):
        app_id = entry.get("id", "?")
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
            for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
                loc = ".".join(str(p) for p in err.path) or "(manifest)"
                errors.append(f"{rel}: {loc}: {err.message}")
    for path in sorted(MANIFESTS.glob("*/*.json")):
        if path.resolve() not in listed:
            errors.append(f"{path.relative_to(ROOT)} is not listed in index.json")
    if base:
        errors += immutability(base)
    return errors


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
            errors.append(f"{rel}: published manifest was changed; publish a new version instead")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate the extension index")
    ap.add_argument("--base", help="git ref whose manifests must be unchanged (e.g. origin/main)")
    errors = check(ap.parse_args().base)
    for e in errors:
        print(f"error: {e}")
    print("index OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
