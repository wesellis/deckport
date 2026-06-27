"""Load, validate, and apply per-game recipes (the TOML in ``recipes/``).

A recipe pins what auto-detection can't guess: the exact binary, required data
files, launch options, and (for Windows games) the Proton config. The importer
uses it to override its heuristics for a matched folder. Same schema the website
and ``schema.json`` use — see ``deckport-recipes/RECIPE_FORMAT.md``.

TOML parsing needs ``tomllib`` (Python 3.11+) or the ``tomli`` backport. When
neither is present the core importer still runs — recipe features just disable
gracefully, so the single-file build stays usable on older Python.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from .detect import clean_name

try:
    import tomllib as _toml  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - exercised on <3.11
    try:
        import tomli as _toml  # optional backport (PC tools)
    except ModuleNotFoundError:
        _toml = None

__all__ = [
    "Recipe",
    "TOML_AVAILABLE",
    "ENGINES",
    "STATUSES",
    "TYPES",
    "FORBIDDEN_TOKENS",
    "load",
    "load_dir",
    "validate",
    "forbidden_content",
    "unsafe_launch_options",
    "match_folder",
    "missing_requires",
]

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
