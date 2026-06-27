#!/usr/bin/env python3
"""deckport.py - register portable Linux games (Godot, LOVE, generic ELF) as
non-Steam shortcuts on a Steam Deck / SteamOS machine.

AUTO-GENERATED single-file build of the ``deckport`` package — do not edit by
hand. Edit ``src/deckport/`` and run ``python scripts/build_single_file.py``.
Pure standard library by design, so it runs on SteamOS's read-only root.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import argparse
import glob
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib

__version__ = "0.1.0"


# ======================================================================
# vdf
# ======================================================================

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

# ======================================================================
# textvdf
# ======================================================================

def _tokenize(text: str):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":  # // comment to EOL
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c in "{}":
            yield c
            i += 1
            continue
        if c == '"':
            i += 1
            buf = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    nxt = text[i + 1]
                    buf.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt))
                    i += 2
                else:
                    buf.append(text[i])
                    i += 1
            i += 1  # closing quote
            yield ('"', "".join(buf))
            continue
        # bare (unquoted) token — rare in config.vdf, supported for robustness
        j = i
        while j < n and text[j] not in ' \t\r\n{}"':
            j += 1
        yield ('"', text[i:j])
        i = j


def _parse_map(tokens, depth=0) -> dict:
    out: dict = {}
    for tok in tokens:
        if tok == "}":
            return out
        if tok == "{":
            raise ValueError("unexpected '{' (expected a key)")
        key = tok[1]
        nxt = next(tokens)
        if nxt == "{":
            out[key] = _parse_map(tokens, depth + 1)
        elif isinstance(nxt, tuple):
            out[key] = nxt[1]
        else:
            raise ValueError(f"unexpected token after key {key!r}: {nxt!r}")
    if depth != 0:
        raise ValueError("unexpected end of input inside a block")
    return out


def loads(text: str) -> dict:
    """Parse text KeyValues into nested dicts (last value wins on duplicate keys)."""
    return _parse_map(_tokenize(text))


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


def dumps(d: dict, indent: int = 0) -> str:
    """Serialize nested dicts to tab-indented Steam-style text KeyValues."""
    pad = "\t" * indent
    lines = []
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f'{pad}"{_esc(str(k))}"')
            lines.append(f"{pad}{{")
            lines.append(dumps(v, indent + 1))
            lines.append(f"{pad}}}")
        else:
            lines.append(f'{pad}"{_esc(str(k))}"\t\t"{_esc(str(v))}"')
    return "\n".join(line for line in lines if line != "")


def load_file(path: str) -> dict:
    import os

    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8", errors="replace") as f:
        return loads(f.read())


def save_file(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(data) + "\n")

# ======================================================================
# appid
# ======================================================================

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

# ======================================================================
# detect
# ======================================================================

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

# ======================================================================
# steam
# ======================================================================

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

# ======================================================================
# artwork
# ======================================================================

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

# ======================================================================
# recipe
# ======================================================================

try:
    import tomllib as _toml  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - exercised on <3.11
    try:
        import tomli as _toml  # optional backport (PC tools)
    except ModuleNotFoundError:
        _toml = None


TOML_AVAILABLE = _toml is not None
ENGINES = {"godot", "love", "unity", "gamemaker", "clickteam", "clickteam-fusion",
           "renpy", "openbor", "gzdoom", "unreal", "ue3", "source", "native", "other"}
STATUSES = {"unverified", "needs-test", "working", "borked"}
TYPES = {"native", "proton"}

# The content line (doc 11), enforced: a recipe must never point at game files.
# These tokens flag ROM / abandonware / warez / torrent sources and DRM
# circumvention. Legitimate creator/storefront links (itch.io, gamejolt, GOG,
# Steam, a developer's own site, Reddit/ProtonDB/SteamGridDB) are NOT listed and
# stay allowed — the line is "where to get the game files", not "links at all".
FORBIDDEN_TOKENS = {
    "myabandonware", "abandonware", "emuparadise", "romsmania", "romhustler",
    "romsmode", "romsget", "romspedia", "coolrom", "vimm.net", "edgeemu",
    "wowroms", "gamulator", "retrostic", "freeroms", "loveroms", "romsfun",
    "nicoblog", "ziperto", "dlpsgame", "apunkagames", "oceanofgames",
    "igg-games", "fitgirl", "skidrow", "rutracker", "thepiratebay", "piratebay",
    "1337x", "rarbg", "limetorrents", "nyaa.si", "kickass", "torrentz",
    "nitroblog", "gamestorrent",
    "magnet:?", ".torrent", "keygen", "warez", "no-cd crack", "no-dvd crack",
}


def _iter_strings(obj):
    """Yield every string value anywhere in a nested dict/list (the parsed TOML)."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_strings(v)


def forbidden_content(recipe: "Recipe") -> list[str]:
    """Content-line denylist (doc 11). Scans every string in the recipe for a
    forbidden source/term. Returns human-readable problems (empty = clean)."""
    errs: list[str] = []
    for s in _iter_strings(recipe.raw):
        low = s.lower()
        for tok in FORBIDDEN_TOKENS:
            if tok in low:
                errs.append(f"content-line violation: {tok!r} appears in {s[:80]!r}")
                break
    return errs


@dataclass
class Recipe:
    slug: str
    title: str
    aliases: list[str] = field(default_factory=list)
    type: str = "native"
    engine: str = "other"
    binary: str = ""
    launch_options: str = ""
    requires_files: list[str] = field(default_factory=list)
    proton_version: str = ""  # CompatToolMapping name for proton games
    status: str = "unverified"
    verified_on: str = ""
    source: str = ""  # filename
    raw: dict = field(default_factory=dict)


def _strlist(v) -> list[str]:
    return [str(x) for x in v] if isinstance(v, list) else []


def load(path: str) -> Recipe:
    """Parse one recipe TOML file. Raises RuntimeError if no TOML parser exists."""
    if _toml is None:
        raise RuntimeError(
            "recipe support needs Python 3.11+ (tomllib) or the 'tomli' package"
        )
    with open(path, "rb") as f:
        t = _toml.load(f)
    game = t.get("game", {}) or {}
    launch = t.get("launch", {}) or {}
    proton = t.get("proton", {}) or {}
    meta = t.get("meta", {}) or {}
    slug = str(game.get("slug") or os.path.splitext(os.path.basename(path))[0])
    return Recipe(
        slug=slug,
        title=str(game.get("title") or slug),
        aliases=_strlist(game.get("aliases")),
        type=str(game.get("type") or "native"),
        engine=str(game.get("engine") or "other"),
        binary=str(launch.get("binary") or ""),
        launch_options=str(launch.get("launch_options") or ""),
        requires_files=_strlist(launch.get("requires_files")),
        proton_version=str(proton.get("version") or ""),
        status=str(meta.get("status") or "unverified"),
        verified_on=str(meta.get("verified_on") or ""),
        source=os.path.basename(path),
        raw=t,
    )


def load_dir(recipes_dir: str) -> list[Recipe]:
    """Load every ``*.toml`` (skipping ``_*``) in a directory; bad files are skipped."""
    out: list[Recipe] = []
    try:
        names = sorted(os.listdir(recipes_dir))
    except OSError:
        return out
    for fn in names:
        if fn.endswith(".toml") and not fn.startswith("_"):
            try:
                out.append(load(os.path.join(recipes_dir, fn)))
            except Exception:
                continue
    return out


def validate(recipe: Recipe) -> list[str]:
    """Return a list of human-readable problems (empty = valid). Enforces the
    honest-status rule: ``working`` requires ``verified_on``."""
    errs: list[str] = []
    if not recipe.slug:
        errs.append("missing game.slug")
    if recipe.type not in TYPES:
        errs.append(f"invalid game.type {recipe.type!r} (native|proton)")
    if recipe.engine not in ENGINES:
        errs.append(f"invalid game.engine {recipe.engine!r}")
    if recipe.status not in STATUSES:
        errs.append(f"invalid meta.status {recipe.status!r}")
    if recipe.status == "working" and not recipe.verified_on:
        errs.append("meta.status 'working' requires meta.verified_on (the honest rule)")
    if not recipe.binary:
        errs.append("missing launch.binary")

    # Consistency (doc 05): a Proton title needs a version; borked needs a reason.
    raw = recipe.raw if isinstance(recipe.raw, dict) else {}
    proton = raw.get("proton") or {}
    if recipe.type == "proton" and not str(proton.get("version") or "").strip():
        errs.append("type 'proton' requires proton.version")
    meta = raw.get("meta") or {}
    if recipe.status == "borked" and not str(meta.get("caveats") or "").strip():
        errs.append("status 'borked' requires meta.caveats explaining why")

    # Security: launch_options is written verbatim into Steam's shortcuts.vdf and
    # becomes part of the launch command. Reject shell metacharacters that could
    # chain or substitute a command — none of these ever appear in a legitimate
    # Steam launch option (env assignments, %command%, wrappers, game flags), so
    # this is zero-breakage defence-in-depth for a malicious recipe contribution.
    errs.extend(unsafe_launch_options(recipe.launch_options))

    # Content line (doc 11): no links to game files / ROM sites / DRM bypass.
    errs.extend(forbidden_content(recipe))
    return errs


# Sequences that enable command chaining/substitution in a shell. A Steam launch
# option never legitimately needs any of them.
_LAUNCH_BAD = (";", "|", "&", "`", "$(", "\n", "\r", "\x00")


def unsafe_launch_options(value: str) -> list[str]:
    """Flag shell metacharacters in launch_options (empty list = clean)."""
    found = [tok for tok in _LAUNCH_BAD if tok in (value or "")]
    if found:
        shown = ", ".join(repr(t) for t in found)
        return [f"launch.launch_options has unsafe shell metacharacter(s): {shown}"]
    return []


def match_folder(recipes: list[Recipe], folder_name: str, binary_names: set[str]) -> Recipe | None:
    """Find the recipe for a dropped folder by slug / alias / cleaned name / binary."""
    cleaned = clean_name(folder_name).lower()
    folder_keys = {cleaned, folder_name.lower()}
    bins = {b.lower() for b in binary_names}
    for r in recipes:
        keys = {r.slug.lower(), r.title.lower(), clean_name(r.title).lower()}
        keys |= {a.lower() for a in r.aliases}
        if folder_keys & keys:
            return r
        if r.binary and r.binary.lower() in bins:
            return r
        if bins & {a.lower() for a in r.aliases}:  # an alias may be an exe basename
            return r
    return None


def missing_requires(recipe: Recipe, folder: str) -> list[str]:
    """Required data files (per the recipe) that aren't beside the binary."""
    return [f for f in recipe.requires_files if not os.path.exists(os.path.join(folder, f))]

# ======================================================================
# proton
# ======================================================================

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

# ======================================================================
# importer
# ======================================================================

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

# ======================================================================
# cli
# ======================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="deckport",
        description="Register portable Linux games as non-Steam shortcuts on a Steam Deck.",
    )
    p.add_argument(
        "--games-dir",
        default=os.path.expanduser("~/Games"),
        help="drop directory to scan (default: ~/Games)",
    )
    p.add_argument("--tag", default="Ported Games", help='collection name (default: "Ported Games")')
    p.add_argument("--recipes", default=None, metavar="DIR",
                   help="folder of recipe .toml files to apply (pins binary, launch options, required files)")
    p.add_argument("--remove-missing", action="store_true",
                   help="prune deckport shortcuts/art/Proton mappings for games no longer in the drop dir")
    p.add_argument("--restart-steam", action="store_true",
                   help="relaunch Steam after a successful write (so changes show up immediately)")
    p.add_argument("--dry-run", action="store_true", help="show decisions, write nothing")
    p.add_argument("--user", default=None, help="pick a specific Steam user dir (auto-detected otherwise)")
    p.add_argument("--version", action="version", version=f"deckport {__version__}")
    return p


def _print_result(result, dry_run: bool) -> None:
    print(f"\nshortcuts.vdf: {result.shortcuts_path}")
    print(f"Drop dir:      {result.games_dir}\n")
    for g in result.added:
        bits = []
        if g.recipe:
            bits.append(f"recipe: {g.recipe}")
        if g.proton:
            bits.append(f"Proton: {g.proton}")
        suffix = f"   ({', '.join(bits)})" if bits else ""
        print(f"  + {g.name}{suffix}\n      {g.binary}")
        if g.art:
            print(f"      art: {', '.join(g.art)}")
        if g.proton_note:
            print(f"      ⚠ Proton: {g.proton_note}")
    for name in result.removed:
        print(f"  ✂ removed (no longer in drop dir): {name}")
    for name, why in result.skipped:
        print(f"  - {name}  ({why})")
    if dry_run:
        print("\n[dry-run] nothing written.")
        return
    if not (result.added or result.removed):
        print("\nNothing new to add.")
        return
    if result.backup_path:
        print(f"\nBackup: {result.backup_path}")
    summary = f"Wrote {len(result.added)} new shortcut(s)"
    if result.removed:
        summary += f", removed {len(result.removed)}"
    print(summary + ". Reopen Steam / return to Game Mode.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not os.path.isdir(args.games_dir):
        print(f"Drop directory not found: {args.games_dir}", file=sys.stderr)
        return 2

    shortcuts_path = find_shortcuts_path(args.user)
    if not shortcuts_path:
        print("Could not locate Steam userdata. Is Steam installed for this user?", file=sys.stderr)
        return 2

    if steam_running() and not args.dry_run:
        print("Steam is running — close it first, or your changes will be wiped.", file=sys.stderr)
        return 1

    recipes = None
    if args.recipes:
        from .recipe import TOML_AVAILABLE, load_dir

        if not TOML_AVAILABLE:
            print("note: --recipes needs Python 3.11+ (or 'tomli'); proceeding without recipes.",
                  file=sys.stderr)
        else:
            recipes = load_dir(args.recipes)
            print(f"loaded {len(recipes)} recipe(s) from {args.recipes}")

    result = import_games(
        games_dir=args.games_dir,
        shortcuts_path=shortcuts_path,
        tag=args.tag,
        dry_run=args.dry_run,
        recipes=recipes,
        remove_missing=args.remove_missing,
    )
    _print_result(result, args.dry_run)

    if args.restart_steam and not args.dry_run and result.wrote:
        if restart_steam():
            print("Relaunching Steam…")
        else:
            print("Could not find 'steam' to relaunch — open it yourself.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


if __name__ == "__main__":
    raise SystemExit(main())
