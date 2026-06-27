"""``deckport`` command-line entry point — the Deck-side importer.

Run in Desktop Mode with Steam closed::

    python3 deckport.py            # or: deckport
    python3 deckport.py --dry-run  # show decisions, write nothing
"""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .importer import import_games
from .steam import find_shortcuts_path, restart_steam, steam_running

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="deckport",
        description="Register portable Linux games as non-Steam shortcuts on a Steam Deck.",
    )
    p.add_argument(
        "--games-dir",
        default=os.path.expanduser("~/Games"),
        help="drop directory to scan (default: ~/Games)",
    )
    p.add_argument("--tag", default="Ported Games", help='collection name (default: "Ported Games")')
    p.add_argument("--recipes", default=None, metavar="DIR",
                   help="folder of recipe .toml files to apply (pins binary, launch options, required files)")
    p.add_argument("--remove-missing", action="store_true",
                   help="prune deckport shortcuts/art/Proton mappings for games no longer in the drop dir")
    p.add_argument("--restart-steam", action="store_true",
                   help="relaunch Steam after a successful write (so changes show up immediately)")
    p.add_argument("--dry-run", action="store_true", help="show decisions, write nothing")
    p.add_argument("--user", default=None, help="pick a specific Steam user dir (auto-detected otherwise)")
    p.add_argument("--version", action="version", version=f"deckport {__version__}")
    return p


def _print_result(result, dry_run: bool) -> None:
    print(f"\nshortcuts.vdf: {result.shortcuts_path}")
    print(f"Drop dir:      {result.games_dir}\n")
    for g in result.added:
        bits = []
        if g.recipe:
            bits.append(f"recipe: {g.recipe}")
        if g.proton:
            bits.append(f"Proton: {g.proton}")
        suffix = f"   ({', '.join(bits)})" if bits else ""
        print(f"  + {g.name}{suffix}\n      {g.binary}")
        if g.art:
            print(f"      art: {', '.join(g.art)}")
        if g.proton_note:
            print(f"      ⚠ Proton: {g.proton_note}")
    for name in result.removed:
        print(f"  ✂ removed (no longer in drop dir): {name}")
    for name, why in result.skipped:
        print(f"  - {name}  ({why})")
    if dry_run:
        print("\n[dry-run] nothing written.")
        return
    if not (result.added or result.removed):
        print("\nNothing new to add.")
        return
    if result.backup_path:
        print(f"\nBackup: {result.backup_path}")
    summary = f"Wrote {len(result.added)} new shortcut(s)"
    if result.removed:
        summary += f", removed {len(result.removed)}"
    print(summary + ". Reopen Steam / return to Game Mode.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not os.path.isdir(args.games_dir):
        print(f"Drop directory not found: {args.games_dir}", file=sys.stderr)
        return 2

    shortcuts_path = find_shortcuts_path(args.user)
    if not shortcuts_path:
        print("Could not locate Steam userdata. Is Steam installed for this user?", file=sys.stderr)
        return 2

    if steam_running() and not args.dry_run:
        print("Steam is running — close it first, or your changes will be wiped.", file=sys.stderr)
        return 1

    recipes = None
    if args.recipes:
        from .recipe import TOML_AVAILABLE, load_dir

        if not TOML_AVAILABLE:
            print("note: --recipes needs Python 3.11+ (or 'tomli'); proceeding without recipes.",
                  file=sys.stderr)
        else:
            recipes = load_dir(args.recipes)
            print(f"loaded {len(recipes)} recipe(s) from {args.recipes}")

    result = import_games(
        games_dir=args.games_dir,
        shortcuts_path=shortcuts_path,
        tag=args.tag,
        dry_run=args.dry_run,
        recipes=recipes,
        remove_missing=args.remove_missing,
    )
    _print_result(result, args.dry_run)

    if args.restart_steam and not args.dry_run and result.wrote:
        if restart_steam():
            print("Relaunching Steam…")
        else:
            print("Could not find 'steam' to relaunch — open it yourself.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
