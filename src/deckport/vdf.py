"""Binary VDF (KeyValues) reader/writer for Steam's ``shortcuts.vdf``.

The format is a tiny tagged binary tree:

    0x00  <key>\\0 ...map... 0x08   nested map (0x08 closes it)
    0x01  <key>\\0 <value>\\0        UTF-8 string
    0x02  <key>\\0 <int32-LE>        signed 32-bit int

The whole file is::

    0x00 "shortcuts" \\0  ...map...  0x08 0x08

Design rule: writing must be **byte-for-byte idempotent** — load → save → load
must be stable, and we must never corrupt existing entries. Only the standard
library is used so this module can run on the Deck unchanged.
"""
from __future__ import annotations

import struct

__all__ = ["load_shortcuts", "save_shortcuts", "loads", "dumps"]


def _read_cstr(buf: bytes, pos: int) -> tuple[str, int]:
    end = buf.index(b"\x00", pos)
    return buf[pos:end].decode("utf-8", "replace"), end + 1


def _read_map(buf: bytes, pos: int) -> tuple[dict, int]:
    out: dict = {}
    while True:
        t = buf[pos]
        pos += 1
        if t == 0x08:  # end of map
            return out, pos
        key, pos = _read_cstr(buf, pos)
        if t == 0x00:
            val, pos = _read_map(buf, pos)
        elif t == 0x01:
            val, pos = _read_cstr(buf, pos)
        elif t == 0x02:
            val = struct.unpack_from("<i", buf, pos)[0]
            pos += 4
        else:
            raise ValueError(f"Unknown VDF type byte {t:#x} at offset {pos - 1}")
        out[key] = val


def _write_map(d: dict) -> bytes:
    out = bytearray()
    for k, v in d.items():
        key = k.encode("utf-8")
        if isinstance(v, dict):
            out += b"\x00" + key + b"\x00" + _write_map(v) + b"\x08"
        elif isinstance(v, bool):
            # bool is a subclass of int; treat it as int32 (0/1) explicitly.
            out += b"\x02" + key + b"\x00" + struct.pack("<I", int(v) & 0xFFFFFFFF)
        elif isinstance(v, int):
            out += b"\x02" + key + b"\x00" + struct.pack("<I", v & 0xFFFFFFFF)
        else:
            out += b"\x01" + key + b"\x00" + str(v).encode("utf-8") + b"\x00"
    return bytes(out)


def loads(buf: bytes) -> dict:
    """Parse the raw bytes of a shortcuts.vdf, returning the ``shortcuts`` map."""
    if not buf:
        return {}
    pos = 0
    _t = buf[pos]
    pos += 1  # 0x00
    _root_key, pos = _read_cstr(buf, pos)  # "shortcuts"
    root, _pos = _read_map(buf, pos)
    return root


def dumps(shortcuts_map: dict) -> bytes:
    """Serialize a ``shortcuts`` map back to raw shortcuts.vdf bytes."""
    return b"\x00shortcuts\x00" + _write_map(shortcuts_map) + b"\x08\x08"


def load_shortcuts(path: str) -> dict:
    """Read shortcuts.vdf from ``path``. Missing file → empty map."""
    import os

    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        return loads(f.read())


def save_shortcuts(path: str, shortcuts_map: dict) -> None:
    """Write ``shortcuts_map`` to ``path`` as binary shortcuts.vdf."""
    with open(path, "wb") as f:
        f.write(dumps(shortcuts_map))
