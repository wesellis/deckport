"""``deckport-push`` — the one-command "PC → dressed game in Game Mode" tool.

Optionally fetch artwork, copy a game folder to the Deck over SSH, then run the
importer on the Deck — in one shot::

    deckport-push ~/games/"Cool Game"                       # just transfer
    deckport-push ~/games/"Cool Game" --fetch-art --import  # the full pipeline
    deckport-push ~/games/"Cool Game" --import --dry-run     # show every command

Defaults (host, dest, identity, tag) come from ~/.config/deckport/push.toml.
deckport never fetches or distributes game files — it only moves a folder *you*
already have (decision D8).
"""
from __future__ import annotations

import argparse
import os
import sys

from .config import load_config, resolve
from .transport import have, import_cmd, mkdir_cmd, rsync_cmd, scp_cmd, run

__all__ = ["main", "build_parser"]

# Where the matched recipe is staged on the Deck before the import reads it.
REMOTE_RECIPES = "~/.deckport-recipes"


def _resolve_recipes_dir(arg: str | None) -> str | None:
    """Find a local folder of recipe .toml files: --recipes, $DECKPORT_RECIPES,
    then the repo's deckport-recipes/recipes relative to this file."""
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (
        arg,
        os.environ.get("DECKPORT_RECIPES"),
        os.path.normpath(os.path.join(here, "..", "..", "deckport-recipes", "recipes")),
    ):
        if cand and os.path.isdir(cand):
            return cand
    return None


def _match_local_recipe(folder: str, recipes_dir: str) -> str | None:
    """Path to the recipe .toml that matches ``folder`` (by slug/alias/binary), or None."""
    try:
        from deckport.recipe import TOML_AVAILABLE, load_dir, match_folder
    except Exception:
        return None
    if not TOML_AVAILABLE:
        return None
    recipes = load_dir(recipes_dir)
    base = os.path.basename(os.path.normpath(folder))
    try:
        files = {f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))}
    except OSError:
        files = set()
    r = match_folder(recipes, base, files)
    return os.path.join(recipes_dir, r.source) if r else None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="deckport-push",
        description="Copy a game folder to the Steam Deck and import it, in one command.",
    )
    p.add_argument("folder", help="the game folder to push")
    p.add_argument("--host", help="ssh target, e.g. deck@steamdeck (or set in push.toml)")
    p.add_argument("--dest", help="remote drop dir (default ~/Games)")
    p.add_argument("--tag", help='collection name for the import (default "Ported Games")')
    p.add_argument("--identity", help="ssh private key path")
    p.add_argument("--fetch-art", action="store_true", help="fetch SteamGridDB art into the folder first")
    p.add_argument("--import", dest="do_import", action="store_true",
                   help="run the importer on the Deck after transfer")
    p.add_argument("--recipes", help="local recipe folder to match against "
                   "(default: auto-discover; ships the matched recipe so Proton/launch options apply)")
    p.add_argument("--no-recipes", action="store_true", help="import with auto-detect only (don't ship a recipe)")
    p.add_argument("--config", help="path to push.toml (default ~/.config/deckport/push.toml)")
    p.add_argument("--dry-run", action="store_true", help="print every command, run nothing")
    return p


def _fetch_art(folder: str, api_key_env: str, dry_run: bool) -> None:
    """Best-effort local artwork fetch (skips with a note if unavailable)."""
    key = os.environ.get(api_key_env)
    if not key:
        print(f"  (skipping art: ${api_key_env} not set)")
        return
    try:
        from deckport.detect import clean_name
        from deckport_art.fetch import fetch_into
        from deckport_art.steamgrid import SteamGridDB
    except Exception as exc:
        print(f"  (skipping art: {exc})")
        return
    name = clean_name(os.path.basename(os.path.normpath(folder)))
    if dry_run:
        print(f"  would fetch art for \"{name}\" into {folder}/.deckport-art/")
        return
    res = fetch_into(SteamGridDB(key), name, folder)
    if res.game:
        print(f"  art: matched {res.game.get('name')} — {len(res.written)} image(s)")
    else:
        print(f"  art: no SteamGridDB match for \"{name}\"")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = resolve(args, load_config(args.config))

    if not os.path.isdir(args.folder):
        print(f"not a folder: {args.folder}", file=sys.stderr)
        return 2
    if not cfg.host:
        print("no --host given and none in push.toml (e.g. deck@steamdeck)", file=sys.stderr)
        return 2

    print(f"\ndeckport-push: {os.path.basename(os.path.normpath(args.folder))} -> {cfg.host}:{cfg.dest}")

    if args.fetch_art:
        print("fetching artwork…")
        _fetch_art(args.folder, cfg.api_key_env, args.dry_run)

    print("transferring…")
    if run(mkdir_cmd(cfg.host, cfg.dest, cfg.identity), args.dry_run) != 0:
        print("error: could not create remote dir (check host/ssh)", file=sys.stderr)
        return 1
    if have("rsync"):
        cmd = rsync_cmd(args.folder, cfg.host, cfg.dest, cfg.identity)
    elif have("scp"):
        cmd = scp_cmd(args.folder, cfg.host, cfg.dest, cfg.identity)
    else:
        print("error: neither rsync nor scp found on PATH", file=sys.stderr)
        return 1
    if run(cmd, args.dry_run) != 0:
        print("error: transfer failed", file=sys.stderr)
        return 1

    if args.do_import:
        # Ship the matched recipe so the import applies the pinned binary, launch
        # options and Proton version (not just auto-detect). Best-effort.
        remote_recipes = None
        if not args.no_recipes:
            rdir = _resolve_recipes_dir(args.recipes)
            toml = _match_local_recipe(args.folder, rdir) if rdir else None
            if toml:
                print(f"shipping recipe: {os.path.basename(toml)}")
                run(mkdir_cmd(cfg.host, REMOTE_RECIPES, cfg.identity), args.dry_run)
                ship = rsync_cmd if have("rsync") else scp_cmd
                if run(ship(toml, cfg.host, REMOTE_RECIPES, cfg.identity), args.dry_run) == 0:
                    remote_recipes = REMOTE_RECIPES
                else:
                    print("  (recipe transfer failed — importing with auto-detect only)", file=sys.stderr)
            else:
                print("  (no matching recipe found — importing with auto-detect only)")

        print("importing on the Deck (Steam must be closed there)…")
        rc = run(import_cmd(cfg.host, cfg.dest, cfg.tag, cfg.importer, cfg.identity, remote_recipes), args.dry_run)
        if rc != 0:
            print("error: remote import failed (is Steam closed on the Deck?)", file=sys.stderr)
            return 1

    print("\nDone." + ("" if args.do_import else "  Run the importer on the Deck to finish."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
