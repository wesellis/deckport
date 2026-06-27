"""``deckport-recipe`` — draft a recipe by inspecting a game folder.

    deckport-recipe ~/games/"Cool Game (Linux)"            # write cool-game.toml
    deckport-recipe ~/games/celeste --emit-script          # + celeste.deckport.sh
    deckport-recipe ~/games/celeste --print                # just print, write nothing

The draft starts at status ``needs-test`` — confirm it on a real Deck before
marking ``working``. Recipes describe how to CONFIGURE a game, never where to get it.
"""
from __future__ import annotations

import argparse
import os
import sys

from .render import to_script, to_toml
from .scaffold import scaffold

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="deckport-recipe",
        description="Draft a deckport recipe by inspecting a game folder.",
    )
    p.add_argument("folder", help="the game folder to inspect")
    p.add_argument("--name", help="override the inferred game title")
    p.add_argument("--slug", help="override the inferred slug / filename")
    p.add_argument("--out", default=".", help="output directory (default: current dir)")
    p.add_argument("--emit-script", action="store_true", help="also write <slug>.deckport.sh")
    p.add_argument("--print", dest="to_stdout", action="store_true",
                   help="print the recipe to stdout instead of writing a file")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    return p


def _write(path: str, text: str, force: bool) -> bool:
    if os.path.exists(path) and not force:
        print(f"  exists (use --force): {path}", file=sys.stderr)
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"  wrote {path}")
    return True


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not os.path.isdir(args.folder):
        print(f"not a folder: {args.folder}", file=sys.stderr)
        return 2

    draft = scaffold(args.folder, name=args.name, slug=args.slug)
    toml_text = to_toml(draft)

    if not draft["binary"]:
        print(f'warning: no Linux binary detected in {args.folder} — '
              "this looks like a Proton/Windows game or needs a manual binary.",
              file=sys.stderr)

    if args.to_stdout:
        print(toml_text, end="")
        return 0

    os.makedirs(args.out, exist_ok=True)
    slug = draft["slug"]
    print(f'drafting "{draft["title"]}"  (engine={draft["engine"]}, type={draft["type"]}, '
          f'binary={draft["binary"] or "?"}, status={draft["status"]})')
    ok = _write(os.path.join(args.out, f"{slug}.toml"), toml_text, args.force)
    if args.emit_script:
        _write(os.path.join(args.out, f"{slug}.deckport.sh"), to_script(draft), args.force)

    # Sanity-check the draft against the real validator if TOML support is present.
    try:
        from deckport.recipe import TOML_AVAILABLE, load, validate

        if ok and TOML_AVAILABLE:
            errs = validate(load(os.path.join(args.out, f"{slug}.toml")))
            if errs:
                print("  note: draft needs attention:")
                for e in errs:
                    print(f"    - {e}")
    except Exception:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
