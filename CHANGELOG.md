# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
semantic versioning once it reaches a tagged release.

## [Unreleased]

### Added
- **Steam landscape grids on recipe cards.** Each card on `/recipes/` now shows
  the game's SteamGridDB horizontal capsule as a full-bleed banner. URLs are
  resolved at build time and cached to `web/src/lib/grid-cache.json`
  (`npm run grids`, needs `STEAMGRIDDB_API_KEY`), so the static build stays
  offline/fast and the CDN images are linked, not rehosted. A recipe with no
  match renders without a banner.
- **M7 — release polish.** `--restart-steam` relaunches Steam after a successful
  write (best-effort; Steam must be closed during the import). `release.yml` now
  also builds and attaches the **sdist + wheel** (the pip-installable PC tools)
  alongside the single-file `deckport.py`. New user docs: `docs/FAQ.md`,
  `docs/TROUBLESHOOTING.md`, and `docs/VERIFICATION.md` — the real-Deck checklist
  for promoting recipes to `working`. Linked from the README.
- **M6 — Windows/Proton thin path.** A text-KeyValues reader/writer
  (`deckport.textvdf`) for Steam's `config.vdf`, and `deckport.proton` to
  set/remove a game's **CompatToolMapping**. A `type = "proton"` recipe with a
  `version` now auto-writes the Proton mapping (case-insensitive nav, with a
  backup) as the importer registers it — so Windows games get their Proton set,
  not just a shortcut. New `--remove-missing` prunes deckport-tagged shortcuts,
  grid art, and Proton mappings for games no longer in the drop dir (other tools'
  shortcuts untouched). Tested (text-VDF round-trip, compat-mapping set/remove,
  importer proton + prune); the flat single-file `deckport.py` carries it too.
- **Votes API hardened.** Moved off the deprecated `@app.on_event("startup")` to
  the FastAPI lifespan; added `api/test_votes.py` (vote / switch-no-stack / undo /
  batch / input validation) and a dedicated `api` CI job. The recipe content-line
  denylist now runs in `scripts/validate_recipes.py` so no recipe can link to
  game files.
- **M5 — website (`web/`, Astro static site).** Generates a page per recipe from
  the TOML at build time: searchable/filterable recipe list, per-recipe detail
  (status badge, identity, launch, Proton block, ProtonDB medal, caveats,
  community guides, "browse artwork on SteamGridDB", and a downloadable per-game
  install script). Flat dark palette from the pipeline diagram; responsive. Pure
  static output any host (or nginx on the droplet) serves directly — no Node in
  production.
- **"Suggest a recipe" form (`/suggest`).** Lets non-git users add a recipe: it
  builds a valid TOML in the browser (honest-status rules + a client-side content
  denylist enforced inline) and hands off to GitHub's "propose new file" flow, so
  the submitter opens a PR under their own account — no bot token, no backend, no
  secrets. The PR still passes through CI's full gate. Linked from the nav and as
  the lead path on the Contribute page.
- **Community signal layer (`api/`, decision D10).** A small FastAPI + SQLite
  service serving anonymous "does it run on your Deck?" 👍/👎 per recipe
  (`/api/votes/{slug}`, plus a batch endpoint for card lists). One vote per
  browser (switchable, undoable), IP rate-limited. A vote-driven
  **community-verified** badge lights up at 10 👍 with a positive majority —
  shown separately from the recipe's own honest `status`. Degrades gracefully to
  hidden counts when the API is absent (static-only deploy).
- **Content-line enforcement (decision D11).** `deckport.recipe.validate` now
  runs a **denylist** (`FORBIDDEN_TOKENS`) rejecting ROM/abandonware/warez/
  torrent links and DRM-bypass terms, plus consistency rules (Proton needs a
  `version`; `borked` needs `caveats`). `scripts/validate_recipes.py` also
  validates each recipe against `schema.json` (via `jsonschema` in CI). Tests
  cover the new rules.
- **`GOVERNANCE.md`** — roles and how trusted contributors earn merge rights, so
  the recipe book can be community-run with a near-absent owner.
- **`deploy.yml`** — builds the site on every push (proving a merged recipe
  builds) and deploys site + API to the droplet, gated behind the
  `DEPLOY_ENABLED` repo variable so it stays inert until the server exists.
- Seed recipes: 007 Blood Stone (Proton, ProtonDB Gold), X-Men Origins:
  Wolverine, Mighty Final Fight Forever (OpenBOR, structure-verified to
  `needs-test`), Stairway to Nowhere.
- Recipe `[links]` (protondb / steamgriddb / repeatable community guides) and
  `meta.protondb_tier` medals — reflected in `schema.json`, `RECIPE_FORMAT.md`,
  and the template.

### Added (earlier)
- Deck-side importer: binary detection, execute-bit fix, `shortcuts.vdf`
  read/write with backup, deterministic app-ID generation, bundled-artwork
  placement into the Steam grid folder, collection tagging.
- **M0/M1 — package + tests + CI.** Restructured the single-file importer into a
  modular `src/deckport/` package (`vdf`, `appid`, `detect`, `steam`, `artwork`,
  `importer`, `cli`) with a `deckport` console entry point.
- **Single-file build** (`scripts/build_single_file.py`): flattens the package
  back into the droppable `deckport.py`, with a guard that fails if it pulls in
  anything outside the standard library (the Deck must stay pure-stdlib).
- **Test suite** (`tests/`): VDF round-trip / byte-identical idempotency / the
  high-bit (>2^31) app-ID regression, deterministic app-ID + artwork naming,
  binary detection (Godot export wins, `.so` rejected), and an end-to-end
  importer test (dry-run, real write + backup + art, idempotent re-run).
- **CI** (`.github/workflows/ci.yml`): ruff lint + pytest on Python 3.9/3.11/3.13,
  plus a job asserting `deckport.py` stays in sync with `src/` and stdlib-only.
- **M3 — artwork fetcher (`deckport-art`).** PC-side SteamGridDB client
  (`tools/deckport_art/`, derived from VAPOR) with the one new capability VAPOR
  lacked: **search by name** for non-Steam titles. Resolves a game name → the
  best SteamGridDB match → downloads cover/grid/hero/logo/icon into the game's
  `.deckport-art/` under generic names (the Deck renames them by app ID later).
  Pure-logic matching + a fake-client fetch are unit-tested (no network); the
  fetcher's slots are asserted to match the importer's grid naming. Needs only
  `requests` (no Pillow — images are saved as-is).
- **M2 — recipes are real on the Python side.** `src/deckport/recipe.py` loads,
  validates, and matches recipe TOML; the importer (`--recipes DIR`) now applies a
  matched recipe — honoring the pinned **binary** (over auto-detection), the
  **title**, **launch options** (written into the shortcut), and skipping a game
  with a clear reason when a **required file** is missing. TOML parsing degrades
  gracefully when `tomllib`/`tomli` is absent, so the core importer still runs.
- **`deckport-recipes/schema.json`** — machine schema shared by the importer, the
  website, and CI. **`scripts/validate_recipes.py`** + `recipe-validate.yml`
  validate every recipe on PRs (shape, enums, the honest-status rule that
  `working` requires `verified_on`, and slug == filename). All seed recipes pass.
- **M4 — push tool (`deckport-push`), the one-command demo.** Copies a game
  folder to the Deck over SSH and runs the importer remotely:
  `deckport-push <folder> --host deck@steamdeck --fetch-art --import`. Shells out
  to the system `rsync` (falling back to `scp`) + `ssh` — no SSH-library
  dependency. `--fetch-art` runs the SteamGridDB fetch first so art rides along
  in the transfer; `--dry-run` prints every command. Defaults come from
  `~/.config/deckport/push.toml` (CLI overrides it). The command builders are
  pure + unit-tested (rsync/scp/ssh/mkdir/import argv, quoting, config merge).
  `scripts/deck-enable-ssh.sh` is the post-update SSH re-enable helper. Never
  fetches or distributes game files — only moves a folder you already have.
- **`deckport-recipe` — the recipe scaffolder.** Inspects a real game folder
  (binary, engine, required files) and writes a ready-to-edit recipe TOML at
  `needs-test`; `--emit-script` also writes the matching `.deckport.sh` install
  helper (same format the website generates). Detects Godot (`.x86_64` + `.pck`),
  LÖVE (`.love`), and Windows/Proton (`.exe`, ignoring installers). The draft is
  re-validated through the real validator before it's written. Makes "build a
  recipe → get a script" a one-liner from any game folder, no hand-written TOML.
- Added `openbor` to the recognized engines (a real homebrew engine in use).
- Recipe format and seed recipes (`deckport-recipes/`).
- Interactive pipeline diagram (`deckport_pipeline.jsx`).
- Project README and internal planning set.
- Repository furniture: license, contributing guide, code of conduct, issue and
  PR templates, packaging config.

### Changed
- Name cleanup now strips versions glued to underscores
  (`MiniTroid_v1.2.3` → `MiniTroid`, previously left `MiniTroid v1`).
- Importer accepts `.ico` artwork (SteamGridDB serves icons as `.ico`), so the
  fetched icon is no longer silently dropped.

### Fixed
- `deckport-art` downloaded images through the authenticated API session, which
  the public SteamGridDB CDN rejects with `401`. Downloads are now unauthenticated.
- A single failed artwork download no longer aborts the whole fetch — that slot
  is skipped and reported, the rest proceed.

### Validated
- `deckport-art` exercised against the **live SteamGridDB API**: name search
  (exact + fuzzy + no-match), all five art slots downloaded as real images
  (verified magic bytes), and the full chain `deckport-art → .deckport-art/ →
  importer install` renaming to `{appid}…` grid names. (The two Fixed items above
  were found this way.)

### Notes
- The `shortcuts.vdf` reader/writer is unit-tested for clean round-trips and
  byte-identical idempotent rewrites. The full PC-to-Deck pipeline has not yet
  been verified on real Deck hardware; seed recipes are `unverified` / `needs-test`.
