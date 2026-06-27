"""Name → SteamGridDB game matching, and the slot→query mapping.

All pure logic (no network), so it's unit-testable. The deckport "slots" are the
generic art names the PC side drops into ``<game>/.deckport-art/``; the Deck
renames them to ``{appid}…`` later.
"""
from __future__ import annotations

import difflib
import re

__all__ = ["normalize", "best_match", "SLOT_QUERY", "ext_for", "ART_SLOTS"]

# deckport art slots -> how to ask SteamGridDB for them. ``cover`` and ``grid``
# are both the "grids" endpoint distinguished by dimensions (portrait vs landscape).
SLOT_QUERY: dict[str, dict] = {
    "cover": {"slot": "grid", "dimensions": ["600x900", "342x482", "660x930"]},  # portrait capsule
    "grid": {"slot": "grid", "dimensions": ["460x215", "920x430"]},  # landscape
    "hero": {"slot": "hero", "dimensions": None},
    "logo": {"slot": "logo", "dimensions": None},
    "icon": {"slot": "icon", "dimensions": None},
}
ART_SLOTS = list(SLOT_QUERY)

_MIME_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/x-icon": "ico"}


def normalize(name: str) -> str:
    """Lowercase, drop punctuation/edition noise → for fuzzy comparison."""
    name = name.lower()
    name = re.sub(r"\b(remastered|deluxe|definitive|edition|goty|hd)\b", " ", name)
    name = re.sub(r"[^a-z0-9]+", " ", name)
    return re.sub(r"\s{2,}", " ", name).strip()


def best_match(name: str, candidates: list[dict]) -> dict | None:
    """Pick the best ``{id, name}`` candidate for ``name``.

    Exact normalized match wins; otherwise the highest difflib ratio above a
    floor. SteamGridDB returns candidates already roughly score-ordered, so ties
    keep the API's order (first wins).
    """
    if not candidates:
        return None
    target = normalize(name)
    best, best_score = None, 0.0
    for cand in candidates:
        cand_norm = normalize(str(cand.get("name", "")))
        if cand_norm == target:
            return cand  # exact normalized hit
        score = difflib.SequenceMatcher(None, target, cand_norm).ratio()
        if score > best_score:
            best, best_score = cand, score
    return best if best_score >= 0.5 else None


def ext_for(url: str, mime: str | None = None) -> str:
    """File extension for a downloaded artwork (mime preferred, else from URL)."""
    if mime and mime in _MIME_EXT:
        return _MIME_EXT[mime]
    tail = url.rsplit("/", 1)[-1].split("?", 1)[0]
    if "." in tail:
        ext = tail.rsplit(".", 1)[-1].lower()
        if ext in {"png", "jpg", "jpeg", "webp", "ico"}:
            return "jpg" if ext == "jpeg" else ext
    return "png"
