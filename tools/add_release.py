#!/usr/bin/env python3
"""Add a released extension manifest to the index.

    tools/add_release.py path/to/manifest.json [--published YYYY-MM-DD]

Copies the manifest verbatim to manifests/<id>/<version>.json and updates index.json:
the entry's version list (newest first), its sha256, and `latest`. A published version is
immutable: re-adding identical bytes is a no-op; different bytes for an existing version fail.
Commit the result and open a PR; CI (tools/validate.py) checks it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from indexlib import load_index, manifest_path, save_index, sha256_file, version_key  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--published", default=dt.date.today().isoformat(), help="release date (default: today)")
    args = ap.parse_args()

    data = json.loads(args.manifest.read_text())
    app_id, version = data["id"], data["version"]
    dest = manifest_path(app_id, version)
    if dest.exists():
        if dest.read_bytes() != args.manifest.read_bytes():
            print(f"error: {app_id} {version} is already published with different content; "
                  "publish a new version instead", file=sys.stderr)
            return 1
        print(f"{app_id} {version} already in the index (identical); nothing to do")
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.manifest, dest)

    index = load_index()
    entry = next((e for e in index["extensions"] if e["id"] == app_id), None)
    if entry is None:
        entry = {"id": app_id, "versions": []}
        index["extensions"].append(entry)
    entry["versions"].append({"version": version, "manifest": f"manifests/{app_id}/{version}.json",
                              "sha256": sha256_file(dest), "published": args.published})
    entry["versions"].sort(key=lambda v: version_key(v["version"]), reverse=True)
    entry["latest"] = entry["versions"][0]["version"]
    latest = json.loads(manifest_path(app_id, entry["latest"]).read_text())
    for key in ("name", "publisher", "category", "tagline"):  # listing fields follow the latest version
        entry[key] = latest[key]
    index["extensions"] = sorted(
        ({k: e[k] for k in ("id", "name", "publisher", "category", "tagline", "latest", "versions")}
         for e in index["extensions"]), key=lambda e: e["id"])
    index["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_index(index)
    print(f"added {app_id} {version} (latest: {entry['latest']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
