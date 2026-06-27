"""Orchestration: scan the drop directory and register games as shortcuts.

Pure logic, no argument parsing or printing — :mod:`deckport.cli` drives this so
the importer is unit-testable. The risky write (``shortcuts.vdf``) is backed up
first and only happens when ``dry_run`` is False.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime

from .appid import shortcut_appid, to_signed32, to_unsigned32
from .artwork import install_artwork, remove_artwork
from .detect import clean_name, find_binary
from .proton import installed_compat_tools, normalize_proton, remove_compat_tool, set_compat_tool
from .recipe import Recipe, match_folder, missing_requires
from .steam import config_vdf_for, grid_dir_for
from .vdf import load_shortcuts, save_shortcuts

__all__ = ["AddedGame", "ImportResult", "build_shortcut", "import_games"]

# Default fields for a non-Steam shortcut entry. Booleans are written as int32.
_SHORTCUT_DEFAULTS = {
    "icon": "",
    "ShortcutPath": "",
    "LaunchOptions": "",
    "IsHidden": 0,
    "AllowDesktopConfig": 1,
    "AllowOverlay": 1,
    "openvr": 0,
    "Devkit": 0,
    "DevkitGameID": "",
    "DevkitOverrideAppID": 0,
    "LastPlayTime": 0,
    "FlatpakAppID": "",
}


def build_shortcut(name: str, binary: str, folder: str, tag: str) -> dict:
    """Construct a single shortcuts.vdf entry for a game.

    ``Exe`` and ``StartDir`` are stored quoted (Steam/STL convention). The
    quoted exe string is what feeds the deterministic app ID, so artwork named
    from the same ID matches.
    """
    exe_q = f'"{binary}"'
    start_q = f'"{folder}/"'
    aid = shortcut_appid(exe_q, name)  # unsigned 32-bit
    entry = {
        "appid": to_signed32(aid),  # VDF stores appid as signed int32
        "AppName": name,
        "Exe": exe_q,
        "StartDir": start_q,
    }
    entry.update(_SHORTCUT_DEFAULTS)
    entry["tags"] = {"0": tag}
    return entry


@dataclass
class AddedGame:
    name: str
    binary: str
    appid: int  # unsigned
    art: list[str] = field(default_factory=list)
    recipe: str | None = None  # source filename of the applied recipe, if any
    proton: str | None = None  # resolved CompatToolMapping id set, if a proton game
    proton_note: str = ""  # warning/info from resolving the recipe's Proton version


@dataclass
class ImportResult:
    shortcuts_path: str
    games_dir: str
    added: list[AddedGame] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (folder, reason)
    removed: list[str] = field(default_factory=list)  # names pruned by remove_missing
    backup_path: str | None = None
    wrote: bool = False


def _is_tagged(entry: dict, tag: str) -> bool:
    tags = entry.get("tags")
    return isinstance(tags, dict) and tag in tags.values()


def _prune_missing(shortcuts: dict, tag: str) -> tuple[dict, list[tuple[str, int]]]:
    """Drop deckport-tagged shortcuts whose Exe no longer exists on disk.

    Only touches entries carrying ``tag`` (never other tools' shortcuts), and
    re-keys the survivors to sequential indices. Returns ``(new_shortcuts,
    [(name, unsigned_appid), ...])``.
    """
    kept: dict = {}
    removed: list[tuple[str, int]] = []
    for v in shortcuts.values():
        if not isinstance(v, dict):
            continue
        exe = v.get("Exe", "").strip('"')
        if _is_tagged(v, tag) and exe and not os.path.exists(exe):
            removed.append((v.get("AppName", "?"), to_unsigned32(v.get("appid", 0))))
        else:
            kept[str(len(kept))] = v
    return kept, removed


def import_games(
    games_dir: str,
    shortcuts_path: str,
    tag: str = "Ported Games",
    dry_run: bool = False,
    set_exec_bit: bool = True,
    recipes: list[Recipe] | None = None,
    remove_missing: bool = False,
    proton_config: str | None = None,
) -> ImportResult:
    """Register every game folder under ``games_dir`` into ``shortcuts.vdf``.

    Skips folders with no Linux binary and games already present (matched by Exe).
    When ``recipes`` are supplied, a matched folder uses the recipe's pinned
    binary, launch options, and title; proton recipes also get a Proton
    CompatToolMapping written to ``config.vdf``. ``remove_missing`` prunes
    deckport-tagged shortcuts/art/mappings for games no longer in the drop dir.
    Backs up the VDF before writing.
    """
    recipes = recipes or []
    result = ImportResult(shortcuts_path=shortcuts_path, games_dir=games_dir)
    shortcuts = load_shortcuts(shortcuts_path)
    grid_dir = grid_dir_for(shortcuts_path)
    config_vdf = proton_config or config_vdf_for(shortcuts_path)
    # Installed custom Proton builds (GE-Proton etc.) live one level up from the
    # global config.vdf, in <steam root>/compatibilitytools.d. We use them to
    # resolve a recipe's human Proton version into a name Steam will accept.
    steam_root = os.path.dirname(os.path.dirname(config_vdf))
    compat_tools = installed_compat_tools(steam_root)

    pruned: list[tuple[str, int]] = []
    if remove_missing:
        shortcuts, pruned = _prune_missing(shortcuts, tag)
        result.removed = [name for name, _ in pruned]

    existing_exes = {
        v.get("Exe", "").strip('"')
        for v in shortcuts.values()
        if isinstance(v, dict)
    }

    for entry in sorted(os.listdir(games_dir)):
        folder = os.path.join(games_dir, entry)
        if not os.path.isdir(folder):
            continue
        files = {
            f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))
        }
        recipe = match_folder(recipes, entry, files) if recipes else None

        # A recipe's pinned binary wins (if it's actually present); else auto-detect.
        binary = None
        if recipe and recipe.binary:
            cand = os.path.join(folder, recipe.binary)
            if os.path.isfile(cand):
                binary = cand
        if not binary:
            binary = find_binary(folder)
        if not binary:
            result.skipped.append((entry, "no Linux executable found"))
            continue
        if binary in existing_exes:
            result.skipped.append((entry, "already in Steam"))
            continue
        if recipe:
            miss = missing_requires(recipe, folder)
            if miss:
                result.skipped.append(
                    (entry, f"missing required file(s): {', '.join(miss)} (recipe {recipe.source})")
                )
                continue

        if set_exec_bit and not dry_run:
            os.chmod(binary, 0o755)  # the all-important +x (transfers strip it)

        name = (recipe.title if recipe else "") or clean_name(entry) or entry
        shortcut = build_shortcut(name, binary, folder, tag)
        if recipe and recipe.launch_options:
            shortcut["LaunchOptions"] = recipe.launch_options
        shortcuts[str(len(shortcuts))] = shortcut
        existing_exes.add(binary)
        aid = to_unsigned32(shortcut["appid"])
        art = install_artwork(folder, grid_dir, aid, dry_run=dry_run)
        # Resolve the recipe's Proton version to a real CompatTool id now (so it
        # shows in dry-run too); the write happens after shortcuts.vdf is saved.
        proton_tool, proton_note = (None, "")
        if recipe and recipe.type == "proton":
            proton_tool, proton_note = normalize_proton(recipe.proton_version, compat_tools)
        result.added.append(
            AddedGame(
                name=name, binary=binary, appid=aid, art=art,
                recipe=(recipe.source if recipe else None),
                proton=proton_tool, proton_note=proton_note,
            )
        )

    if dry_run or not (result.added or result.removed):
        return result

    if os.path.exists(shortcuts_path):
        backup = shortcuts_path + ".bak." + datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(shortcuts_path, backup)
        result.backup_path = backup
    save_shortcuts(shortcuts_path, shortcuts)
    result.wrote = True

    # Proton: map each added proton game's appid to its CompatTool (best-effort —
    # a config.vdf hiccup must not undo the shortcut write).
    for g in result.added:
        if g.proton:
            try:
                set_compat_tool(config_vdf, g.appid, g.proton)
            except Exception:
                g.proton = None  # report honestly that it didn't take

    # remove_missing cleanup: drop pruned games' art + compat mappings.
    for _name, aid in pruned:
        remove_artwork(grid_dir, aid)
        try:
            remove_compat_tool(config_vdf, aid)
        except Exception:
            pass
    return result
