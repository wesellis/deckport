"""Tests for the recipe scaffolder (inspect a folder → draft TOML/script)."""
import pytest

from deckport import recipe as rcp
from deckport_recipe.render import to_script, to_toml
from deckport_recipe.scaffold import scaffold, slugify

ELF = b"\x7fELF" + b"\x00" * 4096


def test_slugify():
    assert slugify("Super Mario Bros. Remastered") == "super-mario-bros-remastered"
    assert slugify("X-Men Origins: Wolverine") == "x-men-origins-wolverine"
    assert slugify("!!!") == "game"


def test_scaffold_godot(tmp_path):
    d = tmp_path / "Cool Game (Linux)"
    d.mkdir()
    (d / "CoolGame.x86_64").write_bytes(ELF)
    (d / "CoolGame.pck").write_bytes(b"data")  # godot data -> required
    (d / "libgodot.so").write_bytes(ELF)
    draft = scaffold(str(d))
    assert draft["title"] == "Cool Game"
    assert draft["slug"] == "cool-game"
    assert draft["engine"] == "godot" and draft["type"] == "native"
    assert draft["binary"] == "CoolGame.x86_64"
    assert draft["requires_files"] == ["CoolGame.pck"]
    assert draft["status"] == "needs-test"  # binary found, not launched


def test_scaffold_love(tmp_path):
    d = tmp_path / "MiniTroid"
    d.mkdir()
    (d / "minitroid.love").write_bytes(b"PK\x03\x04love")
    draft = scaffold(str(d))
    assert draft["engine"] == "love" and draft["type"] == "native"
    assert draft["binary"] == "minitroid.love"


def test_scaffold_proton_exe(tmp_path):
    d = tmp_path / "Old Windows Game"
    d.mkdir()
    (d / "Game.exe").write_bytes(b"MZ" + b"\x00" * 2000)
    (d / "unins000.exe").write_bytes(b"MZ" + b"\x00" * 5000)  # installer -> ignored
    draft = scaffold(str(d))
    assert draft["type"] == "proton" and draft["engine"] == "other"
    assert draft["binary"] == "Game.exe"  # not the uninstaller
    assert draft["proton_version"] == "proton_experimental"
    assert draft["status"] == "needs-test"


def test_scaffold_no_binary(tmp_path):
    d = tmp_path / "Just Data"
    d.mkdir()
    (d / "readme.txt").write_text("hi")
    draft = scaffold(str(d))
    assert draft["binary"] == "" and draft["status"] == "unverified"


def test_overrides(tmp_path):
    d = tmp_path / "x"
    d.mkdir()
    (d / "g.x86_64").write_bytes(ELF)
    draft = scaffold(str(d), name="Pretty Name", slug="custom-slug")
    assert draft["title"] == "Pretty Name" and draft["slug"] == "custom-slug"


@pytest.mark.skipif(not rcp.TOML_AVAILABLE, reason="needs tomllib/tomli")
def test_rendered_toml_is_valid_and_round_trips(tmp_path):
    d = tmp_path / "Cool Game (1.0)"
    d.mkdir()
    (d / "CoolGame.x86_64").write_bytes(ELF)
    (d / "CoolGame.pck").write_bytes(b"data")
    draft = scaffold(str(d))
    out = tmp_path / "cool-game.toml"
    out.write_text(to_toml(draft), encoding="utf-8")

    loaded = rcp.load(str(out))
    assert rcp.validate(loaded) == []  # the scaffolded recipe passes validation
    assert loaded.slug == "cool-game"
    assert loaded.binary == "CoolGame.x86_64"
    assert loaded.requires_files == ["CoolGame.pck"]
    assert loaded.status == "needs-test"


def test_rendered_script_native_vs_proton():
    native = to_script({"title": "G", "slug": "g", "engine": "godot", "type": "native",
                        "binary": "g.x86_64", "launch_options": "", "requires_files": ["g.pck"]})
    assert "chmod 0755" in native and '"g.pck"' in native
    assert native.startswith("#!/usr/bin/env bash")

    proton = to_script({"title": "W", "slug": "w", "engine": "other", "type": "proton",
                        "binary": "W.exe", "launch_options": "", "requires_files": [],
                        "proton_version": "GE-Proton9-20"})
    assert "Windows/Proton title" in proton and "GE-Proton9-20" in proton
