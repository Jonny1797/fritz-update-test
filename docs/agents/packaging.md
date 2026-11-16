# Packaging (PyInstaller)

```bash
uv run pyinstaller packaging/fritz_callhistory.spec   # onefile build into dist/
```

`packaging/fritz_callhistory.spec` needs three non-obvious extras:

- `db/migrations/*.sql` as `datas` — loaded at runtime via `importlib.resources`; without them the frozen app starts with no schema.
- `copy_metadata("fritz-callhistory")` as `datas` — the app reads its version via `importlib.metadata`; without the metadata the frozen app shows the fallback `0.0.0`.
- `keyring` backend modules as `hiddenimports` — its runtime backend discovery is invisible to PyInstaller's static analysis.

`packaging/entry_point.py` exists only because `Analysis()` needs a standalone top-level script, not `app.py`'s package-relative imports.

## Release assets and `SHA256SUMS`

The GitHub release workflow checks out with full history and tags (setuptools-scm) and fails the build if the built version differs from the tag. The release job publishes `SHA256SUMS` (`sha256sum` format, both binaries by their release file names) next to the binaries; the Forgejo workflow waits for and mirrors it. The App update verifies downloads against this file.
