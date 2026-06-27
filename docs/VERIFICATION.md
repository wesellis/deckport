# Real-Deck verification checklist

Everything in this repo is tested without hardware (unit tests, a live SteamGridDB
fetch, dry-runs). The one thing that **cannot** be faked is a real Steam Deck
putting a game on screen. This checklist is that last mile. Work through it on an
actual Deck; when a step passes, a recipe earns the right to move to
`status = "working"` with a real `verified_on`.

> The honest rule (see `deckport-recipes/RECIPE_FORMAT.md`): never mark a recipe
> `working` until **you** have run it on a real Deck and recorded the SteamOS
> build. This checklist is how you earn that.

## Before you start

- A Steam Deck (or any SteamOS / Linux machine running Steam).
- One portable Linux game folder you own — a Godot `.x86_64`, a LÖVE `.love`, or
  a generic ELF. (For the Proton path, a Windows game you own.)
- Note your SteamOS build: **Settings → System → about** → record it for `verified_on`.

## 1. Importer puts a game in Game Mode (roadmap verify #1)

1. Desktop Mode. **Fully close Steam** (it rewrites `shortcuts.vdf` on exit).
2. Copy the game folder into `~/Games/`.
3. Put `deckport.py` in your home folder and run:
   ```bash
   python3 ~/deckport.py            # add --dry-run first to preview
   ```
4. Expected: it reports `+ <Game>` with a binary and writes a backup of any
   existing `shortcuts.vdf`.
5. Reopen Steam → switch to **Game Mode** → the game appears in your library
   under the **Ported Games** collection.
6. **Launch it.** ✅ = it boots to gameplay.

- [ ] Game appears in Game Mode
- [ ] Game launches and is playable
- [ ] Re-running the importer is idempotent (no duplicate shortcut)

## 2. Artwork shows up (roadmap verify #2)

1. On your PC: `deckport-art "~/games/<Game>" ` (needs a free `STEAMGRIDDB_API_KEY`).
2. Confirm `<Game>/.deckport-art/` now holds `cover/grid/hero/logo/icon` images.
3. Transfer the folder to the Deck (or use `deckport-push`, step 3) and re-run the
   importer so it copies art into the Steam `grid/` folder.
4. In Game Mode, open the game's page.

- [ ] Portrait capsule (cover) shows in the library grid
- [ ] Hero banner + logo show on the game page
- [ ] Icon shows in the sidebar / recent games

## 3. One-command push (roadmap verify #3)

1. On the Deck once: run `scripts/deck-enable-ssh.sh` (sets a password, enables
   sshd, makes `~/Games`).
2. From your PC, with Steam closed on the Deck:
   ```bash
   deckport-push "~/games/<Game>" --host deck@<deck-ip> --fetch-art --import
   ```
3. Expected: art is fetched, the folder transfers, the importer runs on the Deck,
   and you're told to reopen Game Mode.

- [ ] Transfer completes
- [ ] Remote import runs and reports the added game
- [ ] Game + art appear in Game Mode — the full "PC → dressed game" loop

## 4. Windows / Proton game (M6)

1. Use a `type = "proton"` recipe with a `[proton] version` (e.g.
   `proton_experimental`), applied via `--recipes`.
2. After import, in Steam check **<game> → Properties → Compatibility** — the
   Proton version from the recipe should already be selected.
3. Launch it.

- [ ] CompatToolMapping is set automatically (no manual Proton selection)
- [ ] Game launches under Proton (note DRM/`winetricks` caveats if it doesn't)

## 5. Cleanup (`--remove-missing`)

1. Delete a game's folder from `~/Games/`.
2. Run `python3 ~/deckport.py --remove-missing`.

- [ ] Its shortcut, grid art, and Proton mapping are gone
- [ ] Your other (non-deckport) shortcuts are untouched

## Recording a result

When a game passes steps 1 (and ideally 2), update its recipe:

```toml
[meta]
status      = "working"
verified_on = "SteamOS 3.6.19 — 2026-07-01"   # your build + date
contributor = "yourname"
caveats     = "the one thing the next person needs to know"
```

Then open a PR (or use the website's **Suggest a recipe** form). CI re-checks it;
a maintainer merges. That's how the corpus moves from `needs-test` to `working`.
