"""Install bundled artwork into Steam's grid folder.

The PC side drops generically-named images into ``<game>/.deckport-art/``
(cover/grid/hero/logo/icon). Once the Deck has computed the app ID, we copy them
into ``userdata/<id>/config/grid/`` under the exact ``{appid}{suffix}`` names
Steam expects (see :mod:`deckport.appid`).
"""
from __future__ import annotations

import glob
import os
import shutil

from .appid import ART_SLOTS, art_filename, to_unsigned32

__all__ = ["ART_DIR", "install_artwork", "remove_artwork"]

ART_DIR = ".deckport-art"
# png/jpg for capsules+hero+logo; ico for icons (SteamGridDB serves icons as .ico).
_EXTS = ("png", "jpg", "jpeg", "ico")


def _source_for(src_dir: str, slot: str) -> str | None:
    for ext in _EXTS:
        cand = os.path.join(src_dir, f"{slot}.{ext}")
        if os.path.exists(cand):
            return cand
    return None


def install_artwork(folder: str, grid_dir: str, appid: int, dry_run: bool = False) -> list[str]:
    """Copy art from ``<folder>/.deckport-art/`` into ``grid_dir``.

    Returns the list of grid filenames placed (or that *would* be placed under
    ``dry_run``). ``appid`` may be signed or unsigned; it is normalized.
    """
    appid = to_unsigned32(appid)
    src_dir = os.path.join(folder, ART_DIR)
    if not os.path.isdir(src_dir):
        return []
    if not dry_run:
        os.makedirs(grid_dir, exist_ok=True)
    placed: list[str] = []
    for slot in ART_SLOTS:
        src = _source_for(src_dir, slot)
        if not src:
            continue
        ext = src.rsplit(".", 1)[1]
        dest_name = art_filename(appid, slot, ext)
        dest = os.path.join(grid_dir, dest_name)
        if not dry_run:
            # Clear any other-extension copy for this slot first, so switching
            # cover.png -> cover.jpg doesn't leave a stale {appid}p.png behind.
            stale_glob = os.path.join(grid_dir, art_filename(appid, slot, "*"))
            for stale in glob.glob(stale_glob):
                try:
                    os.remove(stale)
                except OSError:
                    pass
            shutil.copy2(src, dest)
        placed.append(dest_name)
    return placed


def remove_artwork(grid_dir: str, appid: int) -> list[str]:
    """Delete every grid file for ``appid`` (used by ``--remove-missing``)."""
    appid = to_unsigned32(appid)
    removed: list[str] = []
    for slot in ART_SLOTS:
        for path in glob.glob(os.path.join(grid_dir, art_filename(appid, slot, "*"))):
            try:
                os.remove(path)
                removed.append(os.path.basename(path))
            except OSError:
                pass
    return removed
