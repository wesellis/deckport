# deckport

**Drop a portable game on your PC and have it land on your Steam Deck — unlocked, registered with Steam, dressed in real box art, and ready to play in Game Mode — without installing anything.**

> 🌐 **Live recipe book:** [wesellis.github.io/deckport](https://wesellis.github.io/deckport/)

deckport treats self-contained PC games the way an emulator treats ROMs: the game folder is the cartridge, and a small set of tools does the boring work of getting it recognized and presentable on the Deck. It is deliberately small, dependency-light, and scriptable — not another launcher with a GUI to babysit.

It has also grown a **recipe book and website**: a browsable, fact-checked collection of community configs for **delisted, abandoned, and full-game-modded PC games**. Each recipe carries the right Proton or native setup, real SteamGridDB artwork (capsule + cinematic hero), Steam screenshots, the community ProtonDB tier, and an honest tested-status. The importer, the recipe data, and the site all live in this one repo.

---

## Table of contents

- [Why this exists](#why-this-exists)
- [The core idea](#the-core-idea)
- [How it works (the pipeline)](#how-it-works-the-pipeline)
- [The linchpin: one ID names everything](#the-linchpin-one-id-names-everything)
- [What's in this project](#whats-in-this-project)
- [The importer (`deckport.py`)](#the-importer-deckportpy)
- [The recipe system (`deckport-recipes/`)](#the-recipe-system-deckport-recipes)
- [Setup and usage](#setup-and-usage)
- [Verified facts and gotchas](#verified-facts-and-gotchas)
- [Scope: native vs Windows games](#scope-native-vs-windows-games)
- [Roadmap](#roadmap)
- [Honest status](#honest-status)
- [Prior art and credits](#prior-art-and-credits)
- [Support](#support)

---

## Why this exists

Getting a loose, non-Steam game onto a Steam Deck and into Game Mode is more fiddly than it should be. The game has to be copied over, the Linux binary has to be made executable (file transfers strip that), it has to be registered as a non-Steam shortcut by editing a binary file Steam guards, and if you want it to look like a real game in your library you have to hunt down artwork and name the files by an app ID Steam computes internally.

Console ROMs don't have this problem because the hardware is fixed and one emulator covers the whole library. PC games have no fixed target — the "platform" is the OS plus its libraries. But a large and growing class of indie/homebrew games (anything built on **Godot** or **LÖVE**, plus most native-Linux ELF games) is genuinely self-contained: the binary *is* the program. For those, all the friction above is automatable. deckport automates it.

## The core idea

There are two kinds of game from the Deck's point of view:

1. **Native Linux portable games** (Godot `.x86_64`, LÖVE, generic ELF). These run directly — no Proton, no compatibility layer. This is deckport's home turf, where it's genuinely better than the heavier tools.
2. **Windows games** (a delisted retail title, an old disc game). These need a Proton/Wine prefix and, often, redistributables and DRM handling. deckport does **not** try to reinvent that — it defers to mature tools (Lutris, Bottles, Heroic) and at most sets the Proton mapping. See [Scope](#scope-native-vs-windows-games).

## How it works (the pipeline)

The flow splits cleanly across two machines. The PC half does anything that needs dependencies or the internet; the Deck half stays pure Python standard library so it never fights SteamOS's read-only filesystem.

```
YOUR PC                          TRANSFER                 STEAM DECK
─────────────────────            ──────────────           ─────────────────────────────
1. Fetch artwork                 3. Push over SSH          4. Land in ~/Games
   (SteamGridDB by name)            one rsync / SFTP          whole folder, intact
2. Bundle into the folder           carries game + art     5. Detect binary + chmod +x
   .deckport-art/                                          6. Generate ID, write shortcuts.vdf
   cover / hero / logo / icon                              7. Install art into config/grid/
                                                           8. Restart Steam -> Game Mode
```

- **PC side** finds artwork (via SteamGridDB), saves it into the game folder under generic names in a `.deckport-art/` subfolder, then pushes the whole folder to the Deck in a single transfer.
- **Deck side** (`deckport.py`) scans the drop directory, detects the real game binary, sets the execute bit, writes a non-Steam shortcut into `shortcuts.vdf`, and copies the bundled art into Steam's grid folder with the exact names Steam expects.

An interactive diagram of this flow lives in `deckport_pipeline.jsx`.

## The linchpin: one ID names everything

This is the detail that makes the whole thing work without the two halves having to coordinate.

Steam keys both a non-Steam shortcut **and** its artwork off a single app ID. deckport generates that ID deterministically from the executable path and game name (`crc32(exe + name) | 0x80000000`, landing in the range Steam reserves for non-Steam games). Because it's deterministic and the **Deck computes it**, the same number that goes into `shortcuts.vdf` also names the art files:

```
shortcuts.vdf  appid = 3580912219
config/grid/   3580912219p.jpg      (portrait capsule)
               3580912219.jpg       (landscape grid)
               3580912219_hero.jpg  (hero banner)
               3580912219_logo.png  (logo)
```

The PC never needs to know the ID or the Deck's file paths — it just ships generically named art (`cover`, `hero`, `logo`, `icon`), and the Deck renames them once it has computed the ID. This deterministic-ID approach is the same one Steam ROM Manager and SteamTinkerLaunch use, which is why Steam honors a hand-written app ID and matches the art to it.

## What's in this project

```
deckport/
  README.md                  this file
  GOVERNANCE.md              roles + how the community runs the recipe book
  deckport.py                the Deck-side importer, single-file (generated; pure stdlib)
  src/deckport/              the importer as a package (source of truth)
    vdf.py  appid.py  detect.py  steam.py  artwork.py  recipe.py  importer.py  cli.py
  tools/
    deckport_art/            PC-side SteamGridDB artwork fetcher (deckport-art)
    deckport_push/           PC-side push: rsync/scp + remote import over SSH (deckport-push)
    deckport_recipe/         PC-side recipe scaffolder: inspect a folder -> draft TOML + script (deckport-recipe)
  scripts/
    build_single_file.py     flattens src/deckport -> deckport.py (stdlib-only guard)
    validate_recipes.py      CI recipe gate: shape, schema, honest-status, content-line denylist
  tests/                     vdf, appid, detect, importer, art, recipe, scaffold, push
  deckport-recipes/          community per-game configs (can become its own repo)
    README.md  RECIPE_FORMAT.md  schema.json
    recipes/                 _template.toml + the seed corpus (.toml per game)
  web/                       the recipe-book website (Astro static site)
    src/                     pages, components, the TOML->page build, the suggest form
  api/                       small FastAPI + SQLite service: anonymous 👍/👎 votes
  deckport_pipeline.jsx       interactive React/Tailwind diagram of the flow
```

> The package in `src/deckport/` is the source of truth; `deckport.py` is the
> flattened single file you actually drop on the Deck. Edit the package, then run
> `python scripts/build_single_file.py` to regenerate `deckport.py` (CI enforces
> they stay in sync and that the single file imports nothing outside the stdlib).

## The importer (`deckport.py`)

A single self-contained script meant to run on the Deck in Desktop Mode. It uses only the Python standard library, which matters because SteamOS's root filesystem is immutable and installing pip packages onto it is painful.

What it does, per game folder under the drop directory:

1. **Detects the binary.** Reads ELF magic, skips shared objects (`.so`), and scores candidates — a Godot `*.x86_64` export wins easily, otherwise it prefers a bare-named ELF, a name resembling the folder, or the largest executable.
2. **Sets the execute bit** (`chmod 0755`). File transfers over SFTP/SMB strip this, and a missing `+x` is the single most common reason a copied-over Linux game silently refuses to launch.
3. **Writes the shortcut.** Parses and rewrites Steam's binary `shortcuts.vdf` directly (it backs the file up first, and re-writes byte-for-byte identically so it never corrupts existing entries), adding an entry with the generated app ID, a tidied display name, the `StartDir` set to the game folder, and a collection tag.
4. **Installs artwork.** If a `.deckport-art/` folder rode along inside the game folder, it copies those images into Steam's grid folder under the matching `{appid}…` names, clearing stale copies for each slot first.

Name cleanup turns folder names like `Super Mario Bros. Remastered (1.0.1) (Linux)` into `Super Mario Bros. Remastered` automatically.

### Flags

```
python3 deckport.py
    --games-dir PATH   drop directory to scan        (default: ~/Games)
    --tag NAME         collection name               (default: "Ported Games")
    --dry-run          show decisions, write nothing
    --user STEAMID3    pick a specific Steam user dir (auto-detected otherwise)
```

Run `--dry-run` first to see exactly which binary and art files it would pick before it touches anything.

## The recipe system (`deckport-recipes/`)

Some games need more than auto-detection — a specific data file beside the binary, a particular Proton version, a launch flag, a LÖVE runtime. A **recipe** is a small TOML file (one per game) that captures that knowledge so the next person doesn't have to rediscover it.

The design avoids running any service: recipes are plain files in a git repo, and contributing is a pull request. **Git is the database and the moderation queue** — no server, no uptime to maintain. It can start as just your own recipes and grow only if other people care.

Every recipe carries a mandatory `status`, and that discipline is the whole point of the database being trustworthy:

| status | meaning |
|---|---|
| `unverified` | auto-generated or guessed; never actually run |
| `needs-test` | structure checked (engine, binary, data files) but not launched |
| `working` | confirmed running on a real Deck — records the SteamOS build |
| `borked` | confirmed it does NOT run, with notes on why |

The full schema is in `deckport-recipes/RECIPE_FORMAT.md`. Recipes describe how to *configure* a game (binary, Proton, winetricks, launch options) — never where to obtain game files, and never anything about defeating copy protection.

The book currently holds a few hundred recipes for delisted, abandoned, and modded titles. Many have been independently fact-checked against community sources (ProtonDB, PCGamingWiki, r/SteamDeck, and the relevant mod/port project pages) — the real binary, the essential per-game fix, the honestly-rated ProtonDB tier, the correct controller story. But **none are `working` yet**: that badge is reserved for a confirmed run on real Deck hardware, which is the one thing community research can't substitute for.

## Setup and usage

One-time setup on the Deck (Desktop Mode terminal):

```bash
passwd                              # set a password for the deck user
sudo systemctl enable --now sshd    # turn on the built-in SSH server
mkdir -p ~/Games                    # the drop directory
```

Copy `deckport.py` to the Deck home folder. Then the repeating loop is two steps:

1. **Push the game.** From the PC, connect over SFTP (WinSCP / FileZilla / `rsync`) to `deck@<deck-ip>` and drop the game's whole folder into `~/Games/`, keeping every file together (binary, data files, and any `.deckport-art/`).
2. **Run the importer with Steam closed.** `python3 ~/deckport.py`. Reopen Steam / return to Game Mode and the games are there, controller-ready, under the **Ported Games** collection.

To make re-runs one-tap from the couch, add `deckport.py` itself as a non-Steam game once so dropping new titles and importing never needs the desktop again.

## Documentation

- [docs/FAQ.md](docs/FAQ.md) — what it is, is it safe, does it touch my games, Windows games, SteamOS updates.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — game not in Game Mode, no/wrong art, exec bit, SSH, Proton, recovery.
- [docs/VERIFICATION.md](docs/VERIFICATION.md) — the real-Deck checklist for promoting recipes to `working`.

## Verified facts and gotchas

These were checked against Valve's own issue tracker, Steam community threads, and the established tools — not assumed.

- **Steam must be closed when the importer runs.** Steam holds `shortcuts.vdf` in memory and rewrites it on exit, so edits made while it's running get wiped. The script refuses to run if Steam is up. Restart Steam afterward to pick up both new shortcuts and new art.
- **SteamOS updates wipe everything outside `/home`.** Enabling SSH and setting a password live on the immutable root filesystem and can be reverted by a system update. Your games, `shortcuts.vdf`, and grid art all live in `/home` and survive — but you may need to re-run the SSH-enable once after a big update. A tiny re-enable script parked on the desktop handles this.
- **Don't launch games by URL.** Valve randomized the Big Picture launch ID per-add, so `steam://rungameid/<id>` can't be computed ahead of time anymore. deckport sidesteps this entirely because you launch by tapping the tile in Game Mode, not via a URL.
- **Removing a game leaves orphans.** Steam does not remove a shortcut's `shortcuts.vdf` entry, compat-tool mapping, or grid art when a non-Steam game is removed. A `--remove-missing` cleanup is on the roadmap.
- **The most likely real-world snag is a specific game, not the pipeline.** A given native build might want a launch flag, a missing shared library, or a data file in the right place. That's per-title troubleshooting — exactly what the recipe system is for.

## Scope: native vs Windows games

deckport's lane is **native Linux portable games**, where it's lightweight and genuinely better than the alternatives. For Windows games it deliberately stops short:

- Recreating a Windows environment on Linux — Wine/Proton prefixes, installing DirectX / Visual C++ / .NET, per-game fixes — is an enormous, well-solved problem owned by **Lutris** and **Bottles**. deckport will not reimplement it.
- For a Windows title, the intended path is to hand off to those tools, or at most have deckport register the shortcut and write the Proton compatibility-tool mapping into `config.vdf`, deferring dependency installs to Lutris/protontricks.
- For delisted disc-era games, the real blocker is usually the DRM (SecuROM and friends don't run under Proton), not the porting. A DRM-free copy of files you own is the practical route. deckport recipes describe prefix configuration only.

## Roadmap

- **Importer (done):** folder scan, engine/binary detection, `chmod`, `shortcuts.vdf` read/write with backup, artwork install, collection tag, dry-run, recipe application, `--remove-missing` cleanup.
- **PC tools (done):** `deckport-art` (SteamGridDB fetcher with search-by-name for non-Steam titles); `deckport-push` (rsync/SSH + remote import in one command); `deckport-recipe` (inspect a folder → draft recipe + install script).
- **Windows/Proton (done, thin):** writes the `config.vdf` Proton compat mapping for Proton recipes; hands off prefix management to Lutris/Bottles by design.
- **Recipe book + website (done):** TOML recipes validated in CI (shape, schema, honest status, content-line denylist); an Astro site that renders a page per recipe, anonymous 👍/👎 votes with a community-verified badge, and a **Suggest a recipe** form that opens a PR for non-git users.
- **Next:** real-Deck end-to-end verification to promote seeds to `working`; tagged releases with the single-file build; broader engine detection (Ren'Py, RPG Maker).

## Honest status

This is a side project, built for the fun of it. The `shortcuts.vdf` reader/writer is tested for clean round-trips and byte-identical idempotent rewrites, and the deterministic-ID + artwork-naming approach is the same one shipping tools rely on. But the full chain has not yet been confirmed on real Deck hardware end to end, and seed recipes start at `unverified` or `needs-test` for exactly that reason. Nothing claims to be `working` until a real Deck says so — community 👍 votes can light up a separate *community-verified* badge, but they never overwrite that honest status.

## Prior art and credits

- **Steam ROM Manager**, **SteamTinkerLaunch** — non-Steam shortcut and artwork management; the deterministic-app-ID pattern.
- **Lutris**, **Bottles**, **Heroic** — the mature way to run Windows games on the Deck via Wine/Proton.
- **ProtonDB** — crowdsourced Proton compatibility data and tiers.
- **SteamGridDB** — the artwork source.
- **VAPOR** — the SteamGridDB artwork engine this project's fetcher is built from.

## Support

deckport is free and ad-free — config-only recipes, real artwork, no game files. If a recipe saved you an evening of fiddling and you feel like chipping in toward hosting and the late-night fact-checking, you can [buy me a coffee](https://ko-fi.com/mookyjooky). Entirely optional.
