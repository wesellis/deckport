"""Set a Proton compatibility tool for a non-Steam game in ``config.vdf``.

For a Windows/Proton recipe, registering the shortcut isn't enough — Steam also
needs a CompatToolMapping entry telling it which Proton to run the ``.exe`` with.
That lives in the text ``config.vdf`` at::

    InstallConfigStore / Software / Valve / Steam / CompatToolMapping / <appid>
        { "name" "proton_experimental"  "config" ""  "priority" "250" }

We navigate case-insensitively (Steam has shipped both ``Valve``/``valve``),
back the file up, and write it back. Steam must be closed (it rewrites
``config.vdf`` on exit). Pure stdlib.
"""
from __future__ import annotations

import os
import re
import shutil

from .textvdf import load_file, save_file

__all__ = [
    "COMPAT_PATH",
    "set_compat_tool",
    "remove_compat_tool",
    "get_compat_tool",
    "installed_compat_tools",
    "normalize_proton",
]

COMPAT_PATH = ["InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping"]

# Valve's built-in CompatToolMapping ids keyed by the human "Proton X.Y" form.
# Steam will NOT accept "Proton 7.0-6" or "GE-Proton" as a mapping name — it
# wants these internal ids (or, for GE, the exact compatibilitytools.d folder).
_VALVE_ALIASES = {
    ("9", None): "proton_9", ("9", "0"): "proton_9",
    ("8", None): "proton_8", ("8", "0"): "proton_8",
    ("7", None): "proton_7", ("7", "0"): "proton_7",
    ("6", "3"): "proton_63",
    ("5", "13"): "proton_513", ("5", None): "proton_5", ("5", "0"): "proton_5",
    ("4", "11"): "proton_411", ("4", "2"): "proton_42",
}


def installed_compat_tools(steam_root: str) -> list[str]:
    """Folder names under ``<steam_root>/compatibilitytools.d`` (GE-Proton et al.).

    These are the only valid non-Valve CompatToolMapping names. Returns [] if the
    directory is absent.
    """
    d = os.path.join(steam_root, "compatibilitytools.d")
    try:
        return [n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n))]
    except OSError:
        return []


def _ge_key(name: str) -> tuple[int, ...]:
    """Numeric sort key so GE-Proton9-20 > GE-Proton8-32 > Proton-7.3-GE-1."""
    return tuple(int(x) for x in re.findall(r"\d+", name)) or (0,)


def normalize_proton(version: str, installed: list[str] | None = None) -> tuple[str | None, str]:
    """Map a recipe's human ``proton.version`` to a valid CompatToolMapping name.

    Returns ``(name, note)``. ``name`` is None when it can't be resolved (e.g.
    a bare "GE-Proton" with no GE build installed) — the caller should then skip
    the mapping and surface ``note``. ``note`` is "" on a clean resolution.

    ``installed`` is the list from :func:`installed_compat_tools` (used to resolve
    bare "GE-Proton" to the newest build and to verify a named GE build exists).
    """
    installed = list(installed or [])
    v = (version or "").strip()
    if not v:
        return None, "no Proton version specified"
    low = v.lower()

    # Already a canonical Valve id ("proton_experimental", "proton_9", …).
    if re.fullmatch(r"proton_(experimental|\d+)", low):
        return low, ""
    if "experimental" in low:
        return "proton_experimental", ""

    # A specific GE / custom build name (has "ge" and a digit): it IS the folder
    # name. Use the installed casing if we can see it; else pass through + warn.
    if "ge" in low and re.search(r"\d", low):
        for t in installed:
            if t.lower() == low:
                return t, ""
        if installed:
            return v, f"'{v}' is not in compatibilitytools.d — install it (e.g. ProtonUp-Qt)"
        return v, ""

    # Bare "GE-Proton" → newest installed GE build.
    if re.fullmatch(r"(ge[\s_-]?proton|proton[\s_-]?ge)", low):
        ge = sorted((t for t in installed if "ge" in t.lower()), key=_ge_key)
        if ge:
            return ge[-1], f"resolved GE-Proton → {ge[-1]}"
        return None, "GE-Proton requested but none is installed — add one via ProtonUp-Qt"

    # Human Valve form: "Proton 7.0-6", "Proton 9", "Proton 6.3"…
    m = re.search(r"proton[\s_-]*(\d+)(?:\.(\d+))?", low)
    if m:
        major, minor = m.group(1), m.group(2)
        name = _VALVE_ALIASES.get((major, minor)) or _VALVE_ALIASES.get((major, None)) or f"proton_{major}"
        note = ""
        if int(major) <= 6:
            note = f"{v} is an older build — make sure it's installed/enabled in Steam"
        return name, note

    # Unknown spec: write it through but flag it so a bad value is visible.
    return v, f"unrecognized Proton spec '{v}' — written as-is; verify it exists in Steam"


def _nav(node: dict, path: list[str], create: bool = False) -> dict | None:
    """Walk ``path`` case-insensitively; create canonical-cased blocks if asked."""
    for key in path:
        child = None
        for existing in node:
            if existing.lower() == key.lower() and isinstance(node[existing], dict):
                child = existing
                break
        if child is None:
            if not create:
                return None
            node[key] = {}
            child = key
        node = node[child]
    return node


def _backup(path: str) -> None:
    if os.path.exists(path):
        shutil.copy2(path, path + ".deckport.bak")


def set_compat_tool(config_path: str, appid: int | str, tool: str, priority: int = 250) -> bool:
    """Map ``appid`` → Proton ``tool`` in config.vdf (creates the file/tree if needed)."""
    if not tool:
        return False
    root = load_file(config_path) or {"InstallConfigStore": {}}
    mapping = _nav(root, COMPAT_PATH, create=True)
    mapping[str(appid)] = {"name": tool, "config": "", "priority": str(priority)}
    _backup(config_path)
    parent = os.path.dirname(config_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    save_file(config_path, root)
    return True


def remove_compat_tool(config_path: str, appid: int | str) -> bool:
    """Drop the mapping for ``appid`` (used by ``--remove-missing``). Returns True if removed."""
    root = load_file(config_path)
    if not root:
        return False
    mapping = _nav(root, COMPAT_PATH, create=False)
    if mapping and str(appid) in mapping:
        del mapping[str(appid)]
        _backup(config_path)
        save_file(config_path, root)
        return True
    return False


def get_compat_tool(config_path: str, appid: int | str) -> str | None:
    """The Proton tool name mapped to ``appid``, or None."""
    mapping = _nav(load_file(config_path) or {}, COMPAT_PATH, create=False)
    entry = mapping.get(str(appid)) if mapping else None
    return entry.get("name") if isinstance(entry, dict) else None
