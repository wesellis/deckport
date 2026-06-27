"""Tests for the push tool's command builders and config merge (no network)."""
from types import SimpleNamespace

from deckport_push import transport as tp
from deckport_push.config import PushConfig, resolve


def test_rsync_cmd():
    cmd = tp.rsync_cmd("/games/Cool Game", "deck@host", "~/Games", identity="/k/id")
    assert cmd[0] == "rsync" and "-a" in cmd
    assert "-e" in cmd and "ssh -i /k/id" in cmd
    assert cmd[-2] == "/games/Cool Game"  # source folder (no trailing slash)
    assert cmd[-1] == "deck@host:~/Games/"  # lands as a subdir of dest


def test_rsync_cmd_no_identity():
    cmd = tp.rsync_cmd("/g/x/", "deck@host", "~/Games")
    assert "ssh" in cmd and cmd[-2] == "/g/x"  # trailing slash stripped


def test_scp_cmd():
    cmd = tp.scp_cmd("/g/x", "deck@host", "~/Games", identity="/k/id")
    assert cmd[:2] == ["scp", "-r"]
    assert "-i" in cmd and "/k/id" in cmd
    assert cmd[-1] == "deck@host:~/Games/"


def test_mkdir_cmd():
    cmd = tp.mkdir_cmd("deck@host", "~/Games", identity="/k/id")
    assert cmd[:3] == ["ssh", "-i", "/k/id"]
    assert cmd[-2] == "deck@host"
    assert cmd[-1] == "mkdir -p ~/Games"  # dest unquoted so the remote shell expands ~


def test_import_remote_command_quotes_tag_not_dest():
    rc = tp.import_remote_command("~/Games", "Ported Games", importer="~/deckport.py")
    assert rc == "python3 ~/deckport.py --games-dir ~/Games --tag 'Ported Games'"
    # dest stays unquoted so the remote shell expands ~; tag is quoted (has a space)


def test_import_cmd():
    cmd = tp.import_cmd("deck@host", "~/Games", "Ported Games")
    assert cmd[0] == "ssh" and cmd[1] == "deck@host"
    assert cmd[2].startswith("python3 ~/deckport.py --games-dir ~/Games")


def test_run_dry_run_prints_and_does_not_execute(capsys):
    rc = tp.run(["rsync", "-a", "x", "y"], dry_run=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert "rsync" in out and out.strip().startswith("$")


# -- config merge -----------------------------------------------------------

def _args(**kw):
    base = dict(host=None, dest=None, tag=None, identity=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_resolve_defaults():
    cfg = resolve(_args(), {})
    assert cfg == PushConfig()  # all defaults
    assert cfg.dest == "~/Games" and cfg.tag == "Ported Games"


def test_resolve_config_then_cli_override():
    config = {"host": "deck@file", "dest": "~/Drop", "tag": "From File",
              "art": {"api_key_env": "SGDB_KEY"}}
    cfg = resolve(_args(host="deck@cli", tag="From CLI"), config)
    assert cfg.host == "deck@cli"  # CLI wins
    assert cfg.tag == "From CLI"  # CLI wins
    assert cfg.dest == "~/Drop"  # falls back to config
    assert cfg.api_key_env == "SGDB_KEY"  # from [art]
