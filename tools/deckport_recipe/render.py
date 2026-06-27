"""Render a recipe draft to TOML, and to a per-game install script.

The TOML matches ``RECIPE_FORMAT.md``/``schema.json``; the script mirrors the
website's ``/scripts/<slug>.deckport.sh`` so local and site output agree.
"""
from __future__ import annotations

__all__ = ["to_toml", "to_script"]


def _s(v: str) -> str:
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _arr(items) -> str:
    return "[" + ", ".join(_s(i) for i in items) + "]"


def to_toml(d: dict) -> str:
    proton = (
        f'version    = {_s(d.get("proton_version", ""))}\n'
        "winetricks = []\n"
        'notes      = ""\n'
    )
    return (
        "[game]\n"
        f'title       = {_s(d["title"])}\n'
        f'slug        = {_s(d["slug"])}\n'
        f"aliases     = {_arr(d.get('aliases', []))}\n"
        f'type        = {_s(d["type"])}\n'
        f'engine      = {_s(d["engine"])}\n'
        'steam_appid = ""\n'
        'sgdb_id     = ""\n'
        "\n[launch]\n"
        f'binary         = {_s(d["binary"])}\n'
        f'launch_options = {_s(d.get("launch_options", ""))}\n'
        f"requires_files = {_arr(d.get('requires_files', []))}\n"
        "\n[proton]\n"
        f"{proton}"
        "\n[art]\n"
        'cover = "auto"\n'
        'hero  = "auto"\n'
        'logo  = "auto"\n'
        'icon  = "auto"\n'
        "\n[meta]\n"
        f'status        = {_s(d["status"])}\n'
        'verified_on   = ""\n'
        'contributor   = ""\n'
        'protondb_tier = ""\n'
        f'caveats       = {_s(d.get("caveats", ""))}\n'
    )


def _shq(v: str) -> str:
    """Escape for a double-quoted bash string."""
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")


def to_script(d: dict) -> str:
    """A self-contained install helper for one game (drops on the Deck, runs there).

    Body-identical to the website's ``/scripts/<slug>.deckport.sh`` endpoint
    (``web/src/pages/scripts/[slug].deckport.sh.ts``) — keep the two in sync so
    a recipe's local and on-site install scripts match.
    """
    if d["type"] == "proton":
        lines = [
            'say "This is a Windows/Proton title. The importer registers the shortcut;"',
            'say "set the Proton version + tweaks yourself (Steam > game > Properties):"',
            f'say "  Proton: {_shq(d.get("proton_version") or "(see the recipe page)")}"',
        ]
        wt = d.get("winetricks") or []
        if wt:
            lines.append(f'say "  winetricks: {_shq(", ".join(wt))}"')
        type_block = "\n".join(lines)
    else:
        type_block = 'chmod 0755 "$GAME_DIR/$BINARY"\nsay "set execute bit on $BINARY"'

    requires = " ".join(f'"{_shq(f)}"' for f in d.get("requires_files", []))
    launch = (
        f'say "launch options to paste into Steam > Properties: {_shq(d["launch_options"])}"'
        if d.get("launch_options")
        else ":"
    )
    return f"""#!/usr/bin/env bash
#
# deckport install helper — {d["title"]}
# status: {d.get("status", "needs-test")} · engine: {d.get("engine", "other")} · type: {d["type"]}
#
# Recipes describe how to CONFIGURE a game — never where to obtain it.
#
# ON YOUR STEAM DECK (Desktop Mode), with STEAM CLOSED:
#   1. Copy the game's whole folder into ~/Games/
#   2. Put the importer in your home folder:  ~/deckport.py
#   3. Run:  bash {d["slug"]}.deckport.sh
#
set -euo pipefail

GAMES_DIR="${{GAMES_DIR:-$HOME/Games}}"
IMPORTER="${{IMPORTER:-$HOME/deckport.py}}"
TAG="${{TAG:-Ported Games}}"

GAME_TITLE="{_shq(d["title"])}"
BINARY="{_shq(d["binary"])}"
GAME_TYPE="{d["type"]}"
REQUIRES=({requires})

say()  {{ printf '  %s\\n' "$*"; }}
die()  {{ printf 'error: %s\\n' "$*" >&2; exit 1; }}

printf '\\n=== deckport: %s ===\\n' "$GAME_TITLE"

[ -d "$GAMES_DIR" ] || die "drop directory $GAMES_DIR not found — create it and copy the game folder in"
[ -f "$IMPORTER" ]  || die "importer not found at $IMPORTER — copy deckport.py to your home folder"

# Refuse to clobber shortcuts.vdf while Steam is running (it rewrites on exit).
if pgrep -x steam >/dev/null 2>&1; then
  die "Steam is running — close it fully first, then re-run this script"
fi

# Locate the folder that holds the game binary.
GAME_DIR=""
if [ -n "$BINARY" ]; then
  GAME_DIR="$(find "$GAMES_DIR" -maxdepth 4 -name "$BINARY" -printf '%h\\n' 2>/dev/null | head -n1 || true)"
fi
[ -n "$GAME_DIR" ] || die "could not find '$BINARY' under $GAMES_DIR — copy the game folder there first"
say "found game folder: $GAME_DIR"

# Required data files must sit beside the binary.
for f in "${{REQUIRES[@]:-}}"; do
  [ -z "$f" ] && continue
  if [ -e "$GAME_DIR/$f" ]; then say "ok: $f present"
  else die "missing required file: $f (must sit beside the binary)"; fi
done

{type_block}

{launch}

say "registering with Steam…"
python3 "$IMPORTER" --games-dir "$GAMES_DIR" --tag "$TAG"

printf '\\nDone. Reopen Steam / return to Game Mode — look under "%s".\\n\\n' "$TAG"
"""
