# Contributing to deckport

Thanks for helping out. There are two kinds of contribution: **recipes** (no
coding needed) and **code/docs**.

## Contributing a recipe

A recipe records how to get one game running on a Steam Deck so the next person
doesn't have to rediscover it.

1. Get the game working on your own Deck.
2. Copy `recipes/_template.toml` to `recipes/<slug>.toml` (slug = lowercase,
   hyphenated title; it must match the filename).
3. Fill it in. See `recipes/RECIPE_FORMAT.md` for the schema.
4. Set an **honest** `status`:
   - `working` only if you ran it on a real Deck — and fill in `verified_on`
     with your SteamOS build. CI will reject `working` without it.
   - `borked` if it doesn't work; say why in `caveats`.
   - `needs-test` / `unverified` otherwise.
5. Open a pull request. CI validates the recipe automatically.

**The content line:** recipes describe how to *configure* a game (binary, Proton
version, winetricks, launch options). They must never include game files, links
to obtain games, or anything about defeating copy protection. This is **enforced
by CI** — a denylist rejects ROM/abandonware/torrent links and DRM-bypass terms,
so such PRs fail automatically. (Linking a creator's own free/official page —
itch.io, GameJolt, GOG, Steam, a dev's site — is fine.)

Who merges recipes, and how you earn merge rights, is in
[GOVERNANCE.md](GOVERNANCE.md) — the project is meant to be community-run.

## Contributing code

1. Fork and branch (`feat/...`, `fix/...`).
2. The Deck-side importer (`src/deckport`, and the flattened `deckport.py`) must
   import **only the Python standard library**. Dependencies belong in the
   PC-side tools (`tools/`). CI enforces the stdlib rule.
3. Add or update tests for anything touching the VDF writers or recipe rules.
4. Run the linter and `pytest` locally; keep CI green.
5. Update docs and `CHANGELOG.md` under "Unreleased".
6. Open a PR using the template.

## Local setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,tools]"
pytest
```

## Reporting

Use the issue templates: a bug report, a recipe request, or a "game not
working" report (include your SteamOS build, the engine, and what you tried).
