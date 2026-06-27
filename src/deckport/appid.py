"""Deterministic non-Steam app IDs and the artwork filename mapping.

Steam keys both a non-Steam shortcut *and* its grid artwork off one 32-bit app
ID. We compute that ID deterministically from the executable string and display
name so the Deck — which writes ``shortcuts.vdf`` — can also name the art files
without the PC side ever needing to know the ID. This is the same scheme Steam
ROM Manager and SteamTinkerLaunch use, which is why Steam honors a hand-written
ID and matches art to it.
"""
from __future__ import annotations

import struct
import zlib

__all__ = [
    "shortcut_appid",
    "to_signed32",
    "to_unsigned32",
    "ART_SLOTS",
    "art_filename",
]


def shortcut_appid(exe: str, appname: str) -> int:
    """Deterministic unsigned 32-bit app ID with the high bit set.

    The high bit (``| 0x80000000``) lands it in the range Steam reserves for
    non-Steam shortcuts. ``exe`` should be the exact string stored in the VDF
    (we pass the quoted form, matching SteamTinkerLaunch's behavior).
    """
    crc = zlib.crc32((exe + appname).encode("utf-8")) & 0xFFFFFFFF
    return crc | 0x80000000


def to_signed32(value: int) -> int:
    """Reinterpret an unsigned 32-bit int as signed (how the VDF stores appid)."""
    return struct.unpack("<i", struct.pack("<I", value & 0xFFFFFFFF))[0]


def to_unsigned32(value: int) -> int:
    """Reinterpret a (possibly signed) 32-bit int as unsigned."""
    return value & 0xFFFFFFFF


# Generic art slot name (what the PC side drops into <game>/.deckport-art/)
# -> the filename suffix Steam expects in userdata/<id>/config/grid/.
# Steam's grid naming: {appid}p (portrait capsule), {appid} (landscape grid),
# {appid}_hero, {appid}_logo, {appid}_icon.
ART_SLOTS: dict[str, str] = {
    "cover": "p",  # portrait library capsule -> {appid}p.<ext>
    "grid": "",  # landscape grid           -> {appid}.<ext>
    "hero": "_hero",
    "logo": "_logo",
    "icon": "_icon",
}


def art_filename(appid: int, slot: str, ext: str) -> str:
    """Grid filename for an art ``slot`` (e.g. 'cover') given the unsigned appid.

    ``appid`` must be the unsigned 32-bit value (use :func:`to_unsigned32`).
    """
    if slot not in ART_SLOTS:
        raise KeyError(f"Unknown art slot {slot!r}; known: {sorted(ART_SLOTS)}")
    return f"{to_unsigned32(appid)}{ART_SLOTS[slot]}.{ext.lstrip('.')}"
