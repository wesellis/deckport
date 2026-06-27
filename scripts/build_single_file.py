#!/usr/bin/env python3
"""Flatten the ``src/deckport`` package into the single-file ``deckport.py``.

The Deck-side workflow is "drop one script on the Deck and run it", so the
package must also exist as one self-contained, **standard-library-only** file.
This script concatenates the modules in dependency order, strips intra-package
imports, hoists the (stdlib) imports to the top, and verifies nothing
third-party snuck in.

Usage:
    python scripts/build_single_file.py            # writes deckport.py
    python scripts/build_single_file.py --check     # fail if deckport.py is stale
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "deckport"
OUT = ROOT / "deckport.py"
# Also published by the website so users can download the importer at /deckport.py
# (the per-game install scripts expect it in the home folder).
PUBLIC = ROOT / "web" / "public" / "deckport.py"

# Dependency order: each module only uses names defined above it once flattened.
MODULES = ["vdf", "textvdf", "appid", "detect", "steam", "artwork", "recipe", "proton", "importer", "cli"]

HEADER = '''#!/usr/bin/env python3
"""deckport.py - register portable Linux games (Godot, LOVE, generic ELF) as
non-Steam shortcuts on a Steam Deck / SteamOS machine.

AUTO-GENERATED single-file build of the ``deckport`` package — do not edit by
hand. Edit ``src/deckport/`` and run ``python scripts/build_single_file.py``.
Pure standard library by design, so it runs on SteamOS's read-only root.
"""
'''


def _strip_module(text: str) -> tuple[list[str], list[str]]:
    """Return (top_level_stdlib_imports, body_lines) for one module's source.

    Drops the module docstring, ``from __future__``, relative imports, ``__all__``
    declarations, and hoists indent-0 stdlib imports out of the body.
    """
    lines = text.splitlines()
    imports: list[str] = []
    body: list[str] = []
    i = 0
    # Skip a leading module docstring.
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith(('"""', "'''")):
        quote = lines[i].lstrip()[:3]
        # single-line docstring?
        if lines[i].count(quote) >= 2 and len(lines[i].strip()) > 3:
            i += 1
        else:
            i += 1
            while i < len(lines) and quote not in lines[i]:
                i += 1
            i += 1  # consume closing line

    skip_all = False
    for line in lines[i:]:
        stripped = line.strip()
        if skip_all:
            # inside a multi-line __all__ = [ ... ]
            if "]" in line:
                skip_all = False
            continue
        if stripped.startswith("from __future__"):
            continue
        if stripped.startswith("__all__"):
            if "]" not in stripped:
                skip_all = True
            continue
        # indent-0 imports (not function-local) get hoisted; relative ones dropped.
        if line and not line[0].isspace() and (
            stripped.startswith("import ") or stripped.startswith("from ")
        ):
            if stripped.startswith("from ."):
                continue  # intra-package import — names live in the flat namespace
            imports.append(stripped)
            continue
        body.append(line)
    return imports, body


def build() -> str:
    version = "0.0.0"
    init_text = (PKG / "__init__.py").read_text(encoding="utf-8")
    for ln in init_text.splitlines():
        if ln.strip().startswith("__version__"):
            version = ln.split("=", 1)[1].strip().strip('"').strip("'")
            break

    all_imports: list[str] = []
    seen: set[str] = set()
    bodies: list[str] = []
    for mod in MODULES:
        text = (PKG / f"{mod}.py").read_text(encoding="utf-8")
        imports, body = _strip_module(text)
        for imp in imports:
            if imp not in seen:
                seen.add(imp)
                all_imports.append(imp)
        bodies.append(f"\n# {'=' * 70}\n# {mod}\n# {'=' * 70}\n")
        bodies.append("\n".join(body).strip("\n"))

    _verify_stdlib_only(all_imports)

    parts = [
        HEADER,
        "from __future__ import annotations\n",
        "\n".join(sorted(all_imports)),
        f'\n__version__ = "{version}"\n',
        "\n".join(bodies),
        '\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n',
    ]
    return "\n".join(parts).rstrip("\n") + "\n"


def _verify_stdlib_only(imports: list[str]) -> None:
    """Fail the build if any hoisted import isn't in the standard library."""
    stdlib = getattr(sys, "stdlib_module_names", None)
    if not stdlib:
        return  # <3.10: skip the guard rather than guess
    bad = []
    for imp in imports:
        top = imp.split()[1].split(".")[0] if imp.startswith("from ") else imp.split()[1].split(".")[0]
        top = top.split(",")[0]
        if top not in stdlib:
            bad.append(imp)
    if bad:
        raise SystemExit(
            "single-file build would pull in non-stdlib imports (Deck must stay "
            "pure stdlib):\n  " + "\n  ".join(bad)
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if deckport.py is stale")
    args = ap.parse_args()
    generated = build()
    if args.check:
        stale = [
            p for p in (OUT, PUBLIC)
            if (p.read_text(encoding="utf-8") if p.exists() else "") != generated
        ]
        if stale:
            print("deckport.py is out of date — run: python scripts/build_single_file.py", file=sys.stderr)
            return 1
        print("deckport.py is up to date.")
        return 0
    OUT.write_text(generated, encoding="utf-8")
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.write_text(generated, encoding="utf-8")
    print(f"Wrote {OUT} and {PUBLIC} ({len(generated.splitlines())} lines) from src/deckport/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
