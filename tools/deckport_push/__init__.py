"""deckport-push — transfer a game folder to the Deck and import it over SSH.

PC side. Shells out to the system ``rsync``/``scp``/``ssh`` (OpenSSH ships on
Win10+/Linux/macOS), so no SSH-library dependency. Never fetches or distributes
game files — it only moves a folder you already have.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
