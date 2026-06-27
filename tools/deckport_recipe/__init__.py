"""deckport-recipe — draft a recipe by inspecting a game folder (PC side).

Inspects a folder (binary, engine, required files), writes a ``needs-test``
recipe TOML, and can emit the matching install script — so people can build
recipes from a real game without hand-writing TOML. Uses only the deckport
package; no third-party deps.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
