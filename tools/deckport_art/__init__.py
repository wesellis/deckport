"""deckport-art — SteamGridDB artwork fetcher (PC side, derived from VAPOR).

Resolves a game *name* to SteamGridDB artwork and writes generic
``.deckport-art/{cover,grid,hero,logo,icon}`` files into a game folder. Uses
``requests`` (a PC-side dependency); the Deck importer stays pure stdlib.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
