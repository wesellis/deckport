#!/usr/bin/env python3
"""Validate every recipe TOML in ``deckport-recipes/recipes/``.

Used by CI on recipe PRs. Checks each file parses, satisfies the shape +
honest-status rules (:func:`deckport.recipe.validate`), and that the slug
matches the filename. Exits non-zero with a per-file report on any problem.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # import the package, not the flat deckport.py

from deckport import recipe as rcp  # noqa: E402

RECIPES = ROOT / "deckport-recipes" / "recipes"
SCHEMA = ROOT / "deckport-recipes" / "schema.json"

# Optional: validate the raw TOML against the richer JSON Schema (slug pattern,
# guide-URL shape, enums, the working→verified_on rule). Installed in CI; if it's
# absent locally we still run the Python shape + content-line checks below.
try:
    import jsonschema  # type: ignore
    _SCHEMA = json.loads(SCHEMA.read_text(encoding="utf-8"))
    _VALIDATOR = jsonschema.Draft7Validator(_SCHEMA)
except Exception:  # ModuleNotFoundError or a bad/missing schema
    _VALIDATOR = None


def _schema_errors(raw: dict) -> list[str]:
    if _VALIDATOR is None:
        return []
    out = []
    for e in sorted(_VALIDATOR.iter_errors(raw), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in e.path) or "(root)"
        out.append(f"schema: {loc}: {e.message}")
    return out


def main() -> int:
    if not rcp.TOML_AVAILABLE:
        print("error: need Python 3.11+ (tomllib) or 'tomli' to validate recipes", file=sys.stderr)
        return 2
    files = sorted(f for f in os.listdir(RECIPES) if f.endswith(".toml") and not f.startswith("_"))
    if not files:
        print("no recipes to validate.")
        return 0

    problems: dict[str, list[str]] = {}
    for fn in files:
        path = RECIPES / fn
        try:
            r = rcp.load(str(path))
        except Exception as exc:
            problems[fn] = [f"failed to parse: {exc}"]
            continue
        errs = rcp.validate(r)
        errs.extend(_schema_errors(r.raw))
        errs.extend(rcp.forbidden_content(r))  # content line (doc 11): no game-file sources
        expected_slug = fn[:-5]  # strip .toml
        if r.slug != expected_slug:
            errs.append(f"game.slug {r.slug!r} must equal the filename slug {expected_slug!r}")
        if errs:
            problems[fn] = list(dict.fromkeys(errs))  # dedupe (validate already runs the content check)

    for fn, errs in problems.items():
        print(f"✗ {fn}")
        for e in errs:
            print(f"    - {e}")
    ok = len(files) - len(problems)
    print(f"\n{ok}/{len(files)} recipes valid" + ("" if not problems else f", {len(problems)} with problems"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
