"""``deckport-art`` — fetch SteamGridDB artwork into a game folder (PC side).

Typical use (the importer later renames these by the computed app ID)::

    export STEAMGRIDDB_API_KEY=...        # free key from steamgriddb.com
    deckport-art ~/games/"Cool Game (Linux)"        # name inferred from folder
    deckport-art --name "Celeste" --into ~/games/celeste
    deckport-art ~/games/celeste --dry-run          # show matches, download nothing
"""
from __future__ import annotations

import argparse
import os
import sys

from deckport.detect import clean_name  # reuse the importer's name cleanup

from .fetch import fetch_into
from .search import ART_SLOTS
from .steamgrid import SteamGridDB, SteamGridError

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="deckport-art",
        description="Fetch SteamGridDB artwork into a game folder's .deckport-art/.",
    )
    p.add_argument("folder", nargs="?", help="game folder to dress (name inferred from it)")
    p.add_argument("--name", help="game name to search (overrides the folder name)")
    p.add_argument("--into", help="destination folder (default: the positional folder)")
    p.add_argument("--api-key", default=os.environ.get("STEAMGRIDDB_API_KEY"),
                   help="SteamGridDB API key (or set STEAMGRIDDB_API_KEY)")
    p.add_argument("--slots", default=",".join(ART_SLOTS),
                   help=f"comma list of slots to fetch (default: {','.join(ART_SLOTS)})")
    p.add_argument("--dry-run", action="store_true", help="show the match, download nothing")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    dest = args.into or args.folder
    name = args.name or (clean_name(os.path.basename(os.path.normpath(args.folder))) if args.folder else None)
    if not name:
        print("give a game folder or --name", file=sys.stderr)
        return 2
    if not dest:
        print("give a game folder or --into for the destination", file=sys.stderr)
        return 2

    slots = [s.strip() for s in args.slots.split(",") if s.strip()]
    unknown = [s for s in slots if s not in ART_SLOTS]
    if unknown:
        print(f"unknown slot(s): {', '.join(unknown)}; known: {', '.join(ART_SLOTS)}", file=sys.stderr)
        return 2

    try:
        client = SteamGridDB(args.api_key)
        result = fetch_into(client, name, dest, slots=slots, dry_run=args.dry_run)
    except SteamGridError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not result.game:
        print(f'no SteamGridDB match for "{name}".')
        return 1
    print(f'matched "{name}" -> {result.game.get("name")} (sgdb id {result.game.get("id")})')
    for slot, fname in result.written.items():
        print(f"  {'would fetch' if args.dry_run else 'fetched'}: {slot} -> .deckport-art/{fname}")
    for slot in result.missing:
        print(f"  no {slot} art available")
    for slot, err in result.errors.items():
        print(f"  {slot}: download failed ({err})")
    if args.dry_run:
        print("[dry-run] nothing downloaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
