"""Inspect a real game folder and draft a recipe (pure logic, testable).

The draft starts at ``needs-test`` when a binary is found — the honest rule says
``working`` only after a real Deck launch, so a scaffolder never claims more than
"structure inspected." Everything here is a best guess for a human to confirm.
"""
from __future__ import annotations

import os
import re

from deckport.detect import clean_name, find_binary, sniff_engine

__all__ = ["slugify", "scaffold"]


def slugify(title: str) -> str:
    """Title → ``lowercase-hyphenated`` slug (matches schema + filename rule)."""
    s = re.sub(r"[^a-z0-9]+", "-", title.lower())
    return s.strip("-") or "game"


_INSTALLER_PREFIXES = ("unins", "setup", "vcredist", "dxsetup", "dotnet", "redist", "crashpad")


def _find_exe(folder: str, title: str) -> str | None:
    """Best-guess game ``.exe`` for a Windows/Proton title (find_binary is ELF-only)."""
    try:
        exes = [
            f for f in os.listdir(folder)
            if f.lower().endswith(".exe")
            and not f.lower().startswith(_INSTALLER_PREFIXES)
            and os.path.isfile(os.path.join(folder, f))
        ]
    except OSError:
        return None
    if not exes:
        return None
    first_word = (title.lower().split() or [""])[0]
    exes.sort(
        key=lambda f: (
            bool(first_word) and first_word in f.lower(),  # name resemblance
            os.path.getsize(os.path.join(folder, f)),  # then biggest
        ),
        reverse=True,
    )
    return exes[0]


def _infer_requires(folder: str, binary_name: str, engine: str) -> list[str]:
    """Light, honest guess at required data files beside the binary."""
    try:
        files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    except OSError:
        return []
    if engine == "godot":
        stem = os.path.splitext(binary_name)[0]
        exact = f"{stem}.pck"
        if exact in files:
            return [exact]
        pcks = [f for f in files if f.lower().endswith(".pck")]
        if len(pcks) == 1:
            return pcks  # a single .pck is almost certainly required
    return []


def scaffold(folder: str, name: str | None = None, slug: str | None = None) -> dict:
    """Produce a recipe draft (the dict the renderer turns into TOML)."""
    base = os.path.basename(os.path.normpath(folder))
    title = name or clean_name(base) or base
    binary = find_binary(folder)  # ELF only
    if not binary:  # maybe a Windows/Proton game — fall back to a .exe
        exe = _find_exe(folder, title)
        binary = os.path.join(folder, exe) if exe else None
    if not binary:  # LÖVE: the .love archive is the runnable artifact
        try:
            loves = [f for f in os.listdir(folder) if f.lower().endswith(".love")]
        except OSError:
            loves = []
        if loves:
            binary = os.path.join(folder, loves[0])
    binary_name = os.path.basename(binary) if binary else ""
    engine, gtype = sniff_engine(folder, binary)
    requires = _infer_requires(folder, binary_name, engine)

    aliases = []
    for a in (base, binary_name):
        if a and a != title and a not in aliases:
            aliases.append(a)

    return {
        "title": title,
        "slug": slug or slugify(title),
        "aliases": aliases,
        "type": gtype,
        "engine": engine,
        "binary": binary_name,
        "launch_options": "",
        "requires_files": requires,
        "proton_version": "proton_experimental" if gtype == "proton" else "",
        "status": "needs-test" if binary else "unverified",
        "caveats": (
            "Auto-scaffolded by inspecting the folder — binary/engine/required files "
            "are guesses. Launch it on a real Deck before marking 'working'."
        ),
    }
