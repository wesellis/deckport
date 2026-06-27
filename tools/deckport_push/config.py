"""Load ``push.toml`` and merge it with CLI args.

Config lives at ``~/.config/deckport/push.toml`` (PC side). It only holds
non-secret defaults — host, dest, identity path, importer path, tag, and the
*name* of the env var that holds the SteamGridDB key (never the key itself).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    import tomllib as _toml  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as _toml
    except ModuleNotFoundError:
        _toml = None

__all__ = ["PushConfig", "default_config_path", "load_config", "resolve"]


@dataclass
class PushConfig:
    host: str | None = None
    dest: str = "~/Games"
    identity: str | None = None
    importer: str = "~/deckport.py"
    tag: str = "Ported Games"
    api_key_env: str = "STEAMGRIDDB_API_KEY"


def default_config_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "deckport", "push.toml")


def load_config(path: str | None = None) -> dict:
    """Parse push.toml → dict (empty if missing or no TOML parser available)."""
    path = path or default_config_path()
    if _toml is None or not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as f:
            return _toml.load(f)
    except Exception:
        return {}


def resolve(args, config: dict | None = None) -> PushConfig:
    """CLI args win over config-file values, which win over defaults."""
    cfg = config or {}
    art = cfg.get("art", {}) or {}
    cli = lambda name: getattr(args, name, None)  # noqa: E731
    return PushConfig(
        host=cli("host") or cfg.get("host"),
        dest=cli("dest") or cfg.get("dest") or "~/Games",
        identity=cli("identity") or cfg.get("identity"),
        importer=cfg.get("importer") or "~/deckport.py",
        tag=cli("tag") or cfg.get("tag") or "Ported Games",
        api_key_env=art.get("api_key_env") or "STEAMGRIDDB_API_KEY",
    )
