# Publishing an extension release

Normally this is the last step of the extension's own `build/release.sh`, and you don't do it by hand.

1. Publish the extension's GitHub release with its three assets: `<id>-<version>.qcow2`, `<id>-<version>.qcow2.sha256` and `manifest.json`. The release must be downloadable without credentials.
2. Validate the manifest with the catalog's full validator. It checks semantic rules that the JSON Schema here can't express:
   ```bash
   cd /home/jeff/platform9/projects/pcd-app-catalog && .venv/bin/python -c "import json,sys; from backend.manifests import validate_manifest; print(validate_manifest(json.load(open(sys.argv[1])))[1] or 'valid')" <path>/manifest.json
   ```
3. Add it to the index on a branch and open a PR:
   ```bash
   gh repo clone jscott-pf9/pcd-extensions /tmp/pcd-extensions && cd /tmp/pcd-extensions
   git switch -c release/<id>-<version>
   pip install jsonschema==4.23.0
   python tools/add_release.py <path>/manifest.json --published <YYYY-MM-DD>
   python tools/validate.py --base origin/main
   git add -A && git commit -m "<id> <version>"
   git push -u origin HEAD && gh pr create --fill
   ```
4. CI (`.github/workflows/validate.yml`) runs `tools/validate.py`. It checks that:
   - the index is consistent and its sha256s match;
   - each manifest's id and version match its path;
   - each manifest validates against the schema;
   - no previously published manifest was changed.

   Merge once it's green.

`tools/add_release.py` copies the manifest verbatim, updates the extension's entry (versions newest first, `latest`, and the listing fields taken from the latest version) and refuses to overwrite a published version with different content.

## The standard

The full set of rules an extension follows (image, `manifest.json`, `config.env`, health endpoint, authentication, releases) is in `APPLIANCE_STANDARD.md`. That file is kept in the projects workspace (`/home/jeff/platform9/projects/APPLIANCE_STANDARD.md`), and the manifest schema detail is in the catalog's `docs/MANIFEST_SPEC.md`.
