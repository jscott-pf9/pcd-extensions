# pcd-extensions

The index of extensions that Platform9 Private Cloud Director can install. PCD's **Extensions** section (admin only) reads `index.json` from here to show the catalog. It never needs to know where each extension's source repo is.

| Extension | Latest | Category |
|---|---|---|
| Hello World | 0.1.1 | Utility & Tools |
| PCD Network Director | 0.6.1 | Networking & Security |
| PCD Ops | 0.4.3 | Operations & Analytics |
| vJailbreak | 0.5.0 | Migration |

## Layout

```
index.json                      every extension: id, name, publisher, category, tagline, latest,
                                and its versions (manifest path, sha256, published date), newest first
manifests/<id>/<version>.json   a verbatim copy of that release's manifest.json
schema/manifest.schema.json     the manifest schema (draft 0.2), from the catalog
tools/add_release.py            add a released manifest and update index.json
tools/validate.py               the checks CI runs on every PR and push
```

## How PCD uses it

1. **Sources.** PCD is configured with one or more index URLs, by default `https://raw.githubusercontent.com/jscott-pf9/pcd-extensions/main/index.json`.
2. **Fetching.** It fetches `index.json` and then each listed manifest, resolved relative to the index. It **checks each manifest's sha256 against the index** before using it.
3. **Installing.** The manifest says where the qcow2 is (the extension's own public release) and how to install it. See [CONTRIBUTING.md](CONTRIBUTING.md#the-standard) for what an extension must provide.
4. **Updates.** "Upgrade available" comes from `latest` here.

## Rules

- **One entry per release.** Each version's manifest is a verbatim copy of the `manifest.json` attached to that release.
- **Published versions are immutable.** To fix something, release a new version. CI rejects any change to an existing file under `manifests/`.
- **No secrets, no code.** Only manifests. Images stay in each extension's own release, so the extension's source repo can be private.
- **Merging is the approval.** An extension appears in PCD only once its PR is merged to `main`.

See [CONTRIBUTING.md](CONTRIBUTING.md) to publish a release.
