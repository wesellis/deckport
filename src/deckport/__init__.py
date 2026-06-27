"""deckport — register portable Linux games as non-Steam shortcuts on a Steam Deck.

The package is split into small, single-purpose modules; :mod:`deckport.cli` is
the ``deckport`` entry point. Everything the Deck runs is pure standard library
so it never has to fight SteamOS's read-only root filesystem.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
