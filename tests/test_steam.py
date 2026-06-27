"""Tests for Steam path derivation and the best-effort restart."""
import os

from deckport import steam


def test_config_vdf_for_derives_steam_root():
    sc = os.path.join("home", "deck", ".steam", "steam", "userdata", "123", "config", "shortcuts.vdf")
    cfg = steam.config_vdf_for(sc)
    # config.vdf lives at <steam root>/config/, not under userdata/<id>/
    assert cfg.endswith(os.path.join("steam", "config", "config.vdf"))
    assert "userdata" not in cfg


def test_grid_dir_pairs_with_shortcuts():
    sc = os.path.join("a", "config", "shortcuts.vdf")
    assert steam.grid_dir_for(sc) == os.path.join("a", "config", "grid")


def test_restart_steam_no_binary(monkeypatch):
    monkeypatch.setattr(steam.shutil, "which", lambda _: None)
    called = []
    monkeypatch.setattr(steam.subprocess, "Popen", lambda *a, **k: called.append(a))
    assert steam.restart_steam() is False
    assert called == []  # never tried to launch


def test_restart_steam_launches_when_present(monkeypatch):
    monkeypatch.setattr(steam.shutil, "which", lambda _: "/usr/bin/steam")
    launched = []

    def fake_popen(args, **kwargs):
        launched.append(args)
        return object()

    monkeypatch.setattr(steam.subprocess, "Popen", fake_popen)
    assert steam.restart_steam() is True
    assert launched == [["steam"]]


def test_restart_steam_swallows_oserror(monkeypatch):
    monkeypatch.setattr(steam.shutil, "which", lambda _: "/usr/bin/steam")

    def boom(*a, **k):
        raise OSError("nope")

    monkeypatch.setattr(steam.subprocess, "Popen", boom)
    assert steam.restart_steam() is False
