"""A small SteamGridDB API v2 client.

Derived from the artwork engine in VAPOR (the same author's Steam grid manager),
trimmed to what deckport needs and with one capability VAPOR lacks: **search by
name**. VAPOR only ever looked games up by their Steam app ID; deckport's titles
are non-Steam, so we resolve a name to a SteamGridDB game id first.

PC-side only — uses ``requests``. The Deck-side importer stays pure stdlib.
"""
from __future__ import annotations

from typing import Any

try:
    import requests
except ImportError as exc:  # pragma: no cover - import-time guard
    raise SystemExit(
        "deckport-art needs the 'requests' package: pip install 'deckport[tools]'"
    ) from exc

__all__ = ["SteamGridDB", "SteamGridError"]

_BASE = "https://www.steamgriddb.com/api/v2"
# Static-image endpoints. deckport never wants animated/webm artwork.
_ART_ENDPOINTS = {"grid": "grids", "hero": "heroes", "logo": "logos", "icon": "icons"}


class SteamGridError(RuntimeError):
    """Any failure talking to SteamGridDB (auth, network, bad response)."""


class SteamGridDB:
    def __init__(self, api_key: str, session: Any = None, timeout: float = 15.0):
        if not api_key:
            raise SteamGridError(
                "no SteamGridDB API key (pass --api-key or set STEAMGRIDDB_API_KEY; "
                "get one free at https://www.steamgriddb.com/profile/preferences/api)"
            )
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "deckport-art/0.1",
                "Accept": "application/json",
            }
        )

    # -- low level -----------------------------------------------------------
    def _get(self, path: str, params: dict | None = None) -> Any:
        try:
            r = self.session.get(f"{_BASE}{path}", params=params, timeout=self.timeout)
        except Exception as exc:  # requests.RequestException and friends
            raise SteamGridError(f"network error on {path}: {exc}") from exc
        if r.status_code == 401:
            raise SteamGridError("SteamGridDB rejected the API key (401).")
        if r.status_code == 404:
            return []
        if r.status_code != 200:
            raise SteamGridError(f"SteamGridDB {r.status_code} on {path}: {r.text[:200]}")
        body = r.json()
        if not body.get("success", False):
            raise SteamGridError(f"SteamGridDB error on {path}: {body.get('errors')}")
        return body.get("data", [])

    # -- public --------------------------------------------------------------
    def search(self, term: str) -> list[dict]:
        """Autocomplete search → list of ``{id, name, ...}`` game candidates."""
        return list(self._get(f"/search/autocomplete/{requests.utils.quote(term)}"))

    def artwork(
        self,
        game_id: int,
        slot: str,
        dimensions: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Static artwork for a SteamGridDB game id and a deckport slot.

        ``slot`` is one of grid/hero/logo/icon (cover is just grid with portrait
        dimensions — the CLI handles that). Animated/NSFW entries are filtered.
        """
        if slot not in _ART_ENDPOINTS:
            raise ValueError(f"unknown art slot {slot!r}")
        params: dict[str, str] = {"types": "static"}
        if dimensions:
            params["dimensions"] = ",".join(dimensions)
        items = self._get(f"/{_ART_ENDPOINTS[slot]}/game/{game_id}", params=params)
        clean = [a for a in items if not a.get("nsfw") and a.get("url")]
        return clean[:limit]

    def download(self, url: str) -> bytes:
        # Images live on the public CDN (cdn*.steamgriddb.com), which rejects the
        # API Bearer header with a 401 — so download WITHOUT the auth session.
        try:
            r = requests.get(
                url, timeout=self.timeout, headers={"User-Agent": "deckport-art/0.1"}
            )
            r.raise_for_status()
            return r.content
        except Exception as exc:
            raise SteamGridError(f"failed to download {url}: {exc}") from exc
