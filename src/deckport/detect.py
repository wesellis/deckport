"""Game binary detection and folder-name cleanup.

deckport's home turf is native Linux portable games, so detection is ELF-first:
read the ELF magic, skip shared objects, and score the remaining executables so
a Godot ``*.x86_64`` export wins easily, otherwise prefer a bare-named ELF, a
name resembling the folder, or the largest binary.
"""
from __future__ import annotations

import os
import re

__all__ = ["clean_name", "is_elf", "score_candidate", "find_binary", "sniff_engine"]

_ELF_MAGIC = b"\x7fELF"


def clean_name(folder_name: str) -> str:
    """Turn a messy folder name into a tidy display name.

    'Super Mario Bros. Remastered (1.0.1) (Linux)' -> 'Super Mario Bros. Remastered'
    """
    name = re.sub(r"\((?:[^()]*)\)", "", folder_name)  # drop (1.0.1), (Linux)...
    name = re.sub(r"[_]+", " ", name)  # underscores -> spaces FIRST so glued
    name = re.sub(r"\bv?\d+(?:\.\d+)+\b", "", name)  # ...versions like _v1.2.3 strip too
    return re.sub(r"\s{2,}", " ", name).strip(" -.")


def is_elf(path: str) -> bool:
    """True if ``path`` begins with the ELF magic bytes."""
    try:
        with open(path, "rb") as f:
            return f.read(4) == _ELF_MAGIC
    except OSError:
        return False


# Score below which a candidate is rejected outright (.so, non-ELF).
REJECT = -100


def score_candidate(folder: str, fn: str, base: str | None = None) -> int:
    """Heuristic score for filename ``fn`` inside ``folder`` being the game binary.

    ``base`` is the cleaned, lowercased folder name (computed if omitted).
    """
    if base is None:
        base = clean_name(os.path.basename(folder)).lower()
    full = os.path.join(folder, fn)
    if fn.endswith(".so"):
        return REJECT  # never a shared lib
    if not is_elf(full):
        return REJECT  # native ELF only
    s = 0
    if fn.endswith(".x86_64"):
        s += 50  # Godot Linux export
    if fn.endswith(".x86_32"):
        s += 40
    if "." not in fn:
        s += 20  # bare ELF name
    if base and base.split() and base.split()[0] in fn.lower():
        s += 15  # name resemblance
    try:
        s += min(os.path.getsize(full) // (1024 * 1024), 20)  # bigger = likelier main
    except OSError:
        pass
    return s


def find_binary(folder: str) -> str | None:
    """Pick the most likely game executable in ``folder``, or None."""
    try:
        files = [
            f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))
        ]
    except OSError:
        return None
    base = clean_name(os.path.basename(folder)).lower()
    ranked = sorted(files, key=lambda fn: score_candidate(folder, fn, base), reverse=True)
    if ranked and score_candidate(folder, ranked[0], base) > REJECT:
        return os.path.join(folder, ranked[0])
    return None


def sniff_engine(folder: str, binary: str | None) -> tuple[str, str]:
    """Best-guess ``(engine, type)`` for a game folder + its binary.

    engine ∈ godot|love|native|other ; type ∈ native|proton. A ``.exe`` is a
    Proton case; ``.x86_64`` is a Godot Linux export; a ``.love`` archive is LÖVE;
    any other ELF is generic native. Heuristic — recipes start at ``needs-test``.
    """
    name = (os.path.basename(binary) if binary else "").lower()
    try:
        files = [f.lower() for f in os.listdir(folder)]
    except OSError:
        files = []
    if name.endswith(".exe"):
        return ("other", "proton")
    if name.endswith(".love") or any(f.endswith(".love") for f in files):
        return ("love", "native")
    if name.endswith((".x86_64", ".x86_32")):
        return ("godot", "native")
    if binary and is_elf(binary):
        return ("native", "native")
    return ("other", "native")
