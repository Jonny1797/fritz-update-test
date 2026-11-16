# Changelog

`CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/en/2.0.0/).

- Add an entry under `[Unreleased]` in the right section (`Added` / `Changed` / `Fixed` / …) for every notable feature or fix.
- Write entries in **English**. Quoted UI labels stay as the literal German string (e.g. "Telefonbuch", "Alle Anrufe").
- On release: rename `[Unreleased]` to `<version> - <date>` and open a fresh `[Unreleased]` above it.
- The version comes **only from the git tag** (setuptools-scm, see ADR 0001). Never write a version into `pyproject.toml` or the changelog tooling; a release is a changelog update plus a tag.
