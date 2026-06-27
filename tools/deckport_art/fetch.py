"""Resolve a game name to SteamGridDB artwork and write generic art files.

The output is ``<dest>/.deckport-art/{slot}.{ext}`` with generic slot names
(cover/grid/hero/logo/icon). The Deck-side importer renames them to ``{appid}…``
once it computes the app ID — so the PC never needs to know the ID.

The client is injected (anything with ``.search/.artwork/.download``), which
keeps this orchestration unit-testable without hitting the network.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field

from deckport.artwork import ART_DIR  # single source of truth for ".deckport-art"

from .search import ART_SLOTS, SLOT_QUERY, best_match, ext_for

__all__ = ["FetchResult", "resolve_game", "fetch_into"]


@dataclass
class FetchResult:
    name: str
    game: dict | None = None
    written: dict[str, str] = field(default_factory=dict)  # slot -> filename
    missing: list[str] = field(default_factory=list)  # no art available
    errors: dict[str, str] = field(default_factory=dict)  # slot -> download error
    dest: str | None = None

    @property
    def ok(self) -> bool:
        return self.game is not None and bool(self.written)


def resolve_game(client, name: str) -> dict | None:
    """Search SteamGridDB and pick the best matching game for ``name``."""
    return best_match(name, client.search(name))


def fetch_into(client, name: str, dest: str, slots: list[str] | None = None, dry_run: bool = False) -> FetchResult:
    """Fetch artwork for ``name`` into ``<dest>/.deckport-art/``.

    Picks the top-ranked static image per slot (SteamGridDB returns them
    score-ordered). Returns a structured :class:`FetchResult`.
    """
    slots = slots or ART_SLOTS
    result = FetchResult(name=name, dest=dest)
    game = resolve_game(client, name)
    result.game = game
    if not game:
        result.missing = list(slots)
        return result

    art_dir = os.path.join(dest, ART_DIR)
    for slot in slots:
        query = SLOT_QUERY[slot]
        items = client.artwork(game["id"], query["slot"], dimensions=query["dimensions"])
        chosen = items[0] if items else None
        if not chosen:
            result.missing.append(slot)
            continue
        ext = ext_for(chosen["url"], chosen.get("mime"))
        filename = f"{slot}.{ext}"
        if not dry_run:
            try:
                data = client.download(chosen["url"])
            except Exception as exc:  # one bad asset shouldn't sink the whole fetch
                result.errors[slot] = str(exc)
                continue
            os.makedirs(art_dir, exist_ok=True)
            for stale in glob.glob(os.path.join(art_dir, f"{slot}.*")):
                try:
                    os.remove(stale)
                except OSError:
                    pass
            with open(os.path.join(art_dir, filename), "wb") as f:
                f.write(data)
        result.written[slot] = filename
    return result
