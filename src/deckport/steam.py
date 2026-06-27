"""Locating Steam's per-user config and checking whether Steam is running.

All paths are Linux/SteamOS oriented (this runs on the Deck). The grid folder
sits next to ``shortcuts.vdf`` inside ``userdata/<id>/config/``.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess

__all__ = [
    "find_shortcuts_path",
    "grid_dir_for",
    "config_vdf_for",
    "steam_running",
    "restart_steam",
]

_USERDATA_CANDIDATES = (
    "~/.steam/steam/userdata",
    "~/.local/share/Steam/userdata",
    "~/.var/app/com.valvesoftware.Steam/.local/share/Steam/userdata",  # Flatpak Steam
)


def _userdata_base() -> str | None:
    for cand in _USERDATA_CANDIDATES:
        path = os.path.expanduser(cand)
        if os.path.isdir(path):
            return path
    return None


def find_shortcuts_path(forced_user: str | None = None, create: bool = True) -> str | None:
    """Return the path to ``shortcuts.vdf`` for the active (or forced) Steam user.

    Picks the most recently used account when several exist. Creates the
    ``config`` directory if ``create`` is True. Returns None if Steam userdata
    can't be found.
    """
    base = _userdata_base()
    if not base:
        return None
    users = [d for d in os.listdir(base) if d.isdigit() and d != "0"]
    if forced_user:
        users = [forced_user] if forced_user in users else []
    if not users:
        return None
    users.sort(key=lambda u: os.path.getmtime(os.path.join(base, u)), reverse=True)
    cfg = os.path.join(base, users[0], "config")
    if create:
        os.makedirs(cfg, exist_ok=True)
    return os.path.join(cfg, "shortcuts.vdf")


def grid_dir_for(shortcuts_path: str) -> str:
    """The grid (artwork) directory that pairs with a ``shortcuts.vdf`` path."""
    return os.path.join(os.path.dirname(shortcuts_path), "grid")


def config_vdf_for(shortcuts_path: str) -> str:
    """The Steam-root ``config/config.vdf`` (holds CompatToolMapping) for a given
    ``shortcuts.vdf``. shortcuts.vdf lives at ``<root>/userdata/<id>/config/`` —
    the global config.vdf is at ``<root>/config/config.vdf``."""
    # shortcuts.vdf -> config -> <id> -> userdata -> <steam root>
    steam_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(shortcuts_path))))
    return os.path.join(steam_root, "config", "config.vdf")


def steam_running() -> bool:
    """True if a process named exactly 'steam' is running (Linux /proc scan)."""
    found = False
    for comm in glob.glob("/proc/*/comm"):
        try:
            with open(comm) as f:
                if f.read().strip() == "steam":
                    found = True
                    break
        except OSError:
            continue
    return found


def restart_steam() -> bool:
    """Best-effort (re)launch of Steam after an import so the changes show up.

    The importer requires Steam to be *closed* while it writes, so this just
    relaunches it for convenience. Detached so it doesn't block the CLI. Returns
    True if the launch was issued, False if no ``steam`` binary is on PATH.
    """
    if not shutil.which("steam"):
        return False
    try:
        subprocess.Popen(
            ["steam"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except OSError:
        return False
