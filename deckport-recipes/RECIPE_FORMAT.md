# deckport recipe format

A recipe is one TOML file per game. It tells the importer how to make a game
run on a Steam Deck and where to file it. Recipes are plain text and live in
`recipes/` — contributing is just a pull request. Git is the database.

Filename = the slug, lowercase with hyphens: `recipes/<slug>.toml`.

## The honest rule

`status` is mandatory and starts at `unverified`. A recipe is only `working`
once a real person has run it on a real Deck and recorded the SteamOS build.
Never upgrade a status you haven't personally confirmed.

| status       | meaning                                                        |
|--------------|----------------------------------------------------------------|
| `unverified` | auto-generated or guessed; never actually run                  |
| `needs-test` | structure checked (engine, binary, data files) but not launched |
| `working`    | confirmed running on a real Deck — `verified_on` is required   |
| `borked`     | confirmed it does NOT run, with notes on why                   |

## Fields

```toml
[game]
title       = "Full Game Title"
slug        = "full-game-title"          # must match the filename
aliases     = ["alt name", "exe basename"]  # used to match a dropped folder
type        = "native"                   # native | proton
engine      = "godot"                    # godot | love | unity | gamemaker | clickteam[-fusion] | renpy | openbor | unreal | ue3 | source | native | other
steam_appid = ""                         # only if it exists on Steam (enables ProtonDB + art lookup)
sgdb_id     = ""                         # SteamGridDB game id, optional (art lookup)

[launch]
binary         = "Game.x86_64"           # native: the ELF to chmod + run. proton: the .exe
launch_options = ""                      # extra args; %command% wrapper allowed
requires_files = []                      # data files that MUST sit beside the binary

[proton]                                 # ignored when type = "native"
version    = ""                          # e.g. "GE-Proton9-20" or "proton_experimental"
winetricks = []                          # e.g. ["vcrun2022", "dxvk"]
notes      = ""

[art]                                    # generic names the PC side writes into .deckport-art/
cover = "auto"                           # "auto" = fetch via sgdb_id / title; or a filename
hero  = "auto"
logo  = "auto"
icon  = "auto"

[links]                                  # optional outbound links — we host nothing
protondb    = ""                         # ProtonDB URL; blank = derive from steam_appid
steamgriddb = ""                         # SteamGridDB page; blank = derive from sgdb_id / title

[[links.guides]]                         # repeatable: community write-ups (Reddit, blogs, video)
title = "r/SteamDeck: getting it to run"
url   = "https://www.reddit.com/r/SteamDeck/comments/..."

[meta]
status        = "unverified"
verified_on   = ""                       # SteamOS build + date, required for "working"
contributor   = ""
protondb_tier = ""                       # platinum|gold|silver|bronze|borked|pending (Steam games only)
caveats       = ""                       # the one thing the next person needs to know
```

## Links and artwork — we host nothing

deckport never rehosts game artwork or game files. Recipes carry *links*:

- **`protondb`** — the ProtonDB report. Leave blank and it's derived from
  `steam_appid`. Only Steam games have one.
- **`steamgriddb`** — the game's SteamGridDB page, where a user picks the
  cover/hero/logo/icon they want. Leave blank and the site derives it from
  `sgdb_id`, or falls back to a name search so there's always a link.
- **`protondb_tier`** — a cached ProtonDB medal (`platinum` … `pending`). It's a
  *community* rating, shown separately from this recipe's own `status`, so a game
  can be ProtonDB Gold while still `unverified` here until someone tests it.
- **`[[links.guides]]`** — repeatable community write-ups (Reddit threads, blog
  posts, videos). deckport links to them; it never reproduces them.

Recipes still **never** link to where game files can be downloaded.

## Notes per engine

- **godot** — native Linux export is a `*.x86_64` ELF. Runs directly, no Proton.
- **love** — needs a `love` runtime on the Deck (Flatpak/AppImage) OR a fused
  Linux AppImage. A Windows-fused `.exe` is a Proton case, not native.
- **native** — any other portable Linux ELF.
- **proton** — Windows game. Set a `version`; list `winetricks` the prefix needs.
  For delisted/disc titles, DRM is usually the real blocker — note it, don't
  describe defeating it. Recipes describe prefix setup, never where to get files.
