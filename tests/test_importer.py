"""End-to-end tests for the importer orchestration against temp dirs.

These exercise the whole local chain (detect -> shortcut -> vdf write -> art
placement -> backup -> idempotent re-run) without a real Deck or Steam.
"""
import os
import stat

import pytest

from deckport import proton, vdf
from deckport.appid import to_unsigned32
from deckport.artwork import ART_DIR
from deckport.importer import build_shortcut, import_games
from deckport.recipe import Recipe

ELF = b"\x7fELF" + b"\x00" * 8192
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture()
def world(tmp_path):
    games = tmp_path / "Games"
    game = games / "Cool Game (1.0) (Linux)"
    art = game / ART_DIR
    art.mkdir(parents=True)
    (game / "Cool Game.x86_64").write_bytes(ELF)
    (game / "libengine.so").write_bytes(ELF)  # must be ignored
    (art / "cover.png").write_bytes(PNG)
    (art / "grid.jpg").write_bytes(PNG)
    (art / "icon.ico").write_bytes(b"\x00\x00\x01\x00" + b"\x00" * 32)  # SGDB icons are .ico
    # an empty folder that should be skipped
    (games / "NotAGame").mkdir()
    shortcuts = tmp_path / "userdata" / "123" / "config" / "shortcuts.vdf"
    shortcuts.parent.mkdir(parents=True)
    return dict(games=str(games), shortcuts=str(shortcuts), grid=str(shortcuts.parent / "grid"))


def test_dry_run_writes_nothing(world):
    res = import_games(world["games"], world["shortcuts"], dry_run=True, set_exec_bit=False)
    assert len(res.added) == 1
    assert res.added[0].name == "Cool Game"
    assert ("NotAGame", "no Linux executable found") in res.skipped
    assert not res.wrote
    assert not os.path.exists(world["shortcuts"])  # nothing written


def test_real_import_writes_shortcut_and_art(world):
    res = import_games(world["games"], world["shortcuts"], tag="Ported Games", set_exec_bit=False)
    assert res.wrote and len(res.added) == 1
    g = res.added[0]

    # shortcut landed and is well-formed
    sc = vdf.load_shortcuts(world["shortcuts"])
    assert len(sc) == 1
    entry = sc["0"]
    assert entry["AppName"] == "Cool Game"
    assert entry["Exe"].endswith('Cool Game.x86_64"')
    assert entry["tags"] == {"0": "Ported Games"}
    assert to_unsigned32(entry["appid"]) == g.appid

    # art placed under {appid} names
    grid = world["grid"]
    assert os.path.exists(os.path.join(grid, f"{g.appid}p.png"))  # cover -> portrait
    assert os.path.exists(os.path.join(grid, f"{g.appid}.jpg"))  # grid -> landscape
    assert os.path.exists(os.path.join(grid, f"{g.appid}_icon.ico"))  # icon -> .ico accepted
    assert sorted(g.art) == sorted([f"{g.appid}.jpg", f"{g.appid}_icon.ico", f"{g.appid}p.png"])


def test_rerun_is_idempotent(world):
    import_games(world["games"], world["shortcuts"], set_exec_bit=False)
    res2 = import_games(world["games"], world["shortcuts"], set_exec_bit=False)
    assert res2.added == []
    assert any(reason == "already in Steam" for _, reason in res2.skipped)
    assert vdf.load_shortcuts(world["shortcuts"]) and len(vdf.load_shortcuts(world["shortcuts"])) == 1


def test_backup_made_on_existing_file(world):
    import_games(world["games"], world["shortcuts"], set_exec_bit=False)  # creates file
    # add a second game, re-run -> should back up the existing vdf
    g2 = os.path.join(world["games"], "Second")
    os.mkdir(g2)
    with open(os.path.join(g2, "second"), "wb") as f:
        f.write(ELF)
    res = import_games(world["games"], world["shortcuts"], set_exec_bit=False)
    assert res.backup_path and os.path.exists(res.backup_path)
    assert len(vdf.load_shortcuts(world["shortcuts"])) == 2


@pytest.mark.skipif(os.name == "nt", reason="POSIX exec-bit semantics")
def test_exec_bit_set(world):
    import_games(world["games"], world["shortcuts"], set_exec_bit=True)
    binary = os.path.join(world["games"], "Cool Game (1.0) (Linux)", "Cool Game.x86_64")
    assert os.stat(binary).st_mode & stat.S_IXUSR


# -- M6: Proton compat mapping + remove-missing ------------------------------

def test_proton_recipe_writes_compat_mapping(tmp_path):
    games = tmp_path / "Games"
    game = games / "Old Win Game"
    game.mkdir(parents=True)
    (game / "Game.exe").write_bytes(b"MZ" + b"\x00" * 2000)
    recipe = Recipe(slug="old-win-game", title="Old Win Game", type="proton",
                    binary="Game.exe", proton_version="proton_experimental",
                    aliases=["Game.exe"], source="old-win-game.toml")
    shortcuts = tmp_path / "userdata" / "9" / "config" / "shortcuts.vdf"
    shortcuts.parent.mkdir(parents=True)
    cfg = tmp_path / "config" / "config.vdf"

    res = import_games(str(games), str(shortcuts), recipes=[recipe],
                       set_exec_bit=False, proton_config=str(cfg))
    assert len(res.added) == 1
    g = res.added[0]
    assert g.binary.endswith("Game.exe")  # the .exe, via the recipe
    assert g.proton == "proton_experimental"
    assert proton.get_compat_tool(str(cfg), g.appid) == "proton_experimental"


def test_remove_missing_prunes_orphans_only(tmp_path):
    games = tmp_path / "Games"
    games.mkdir()
    shortcuts = tmp_path / "userdata" / "9" / "config" / "shortcuts.vdf"
    shortcuts.parent.mkdir(parents=True)
    grid = shortcuts.parent / "grid"
    grid.mkdir()
    cfg = tmp_path / "config" / "config.vdf"

    # A deckport-tagged shortcut whose Exe is gone (orphan), with art + a mapping.
    orphan = build_shortcut("Gone Game", str(games / "gone" / "g.x86_64"), str(games / "gone"), "Ported Games")
    orphan_aid = to_unsigned32(orphan["appid"])
    (grid / f"{orphan_aid}p.png").write_bytes(b"x")
    proton.set_compat_tool(str(cfg), orphan_aid, "proton_experimental")
    # A foreign shortcut (different tag) that must be left alone, also "missing".
    foreign = build_shortcut("Other Tool Game", "/nope/other", "/nope", "SomethingElse")
    vdf.save_shortcuts(str(shortcuts), {"0": orphan, "1": foreign})

    res = import_games(str(games), str(shortcuts), tag="Ported Games",
                       remove_missing=True, set_exec_bit=False, proton_config=str(cfg))
    assert res.removed == ["Gone Game"]
    sc = vdf.load_shortcuts(str(shortcuts))
    names = {v["AppName"] for v in sc.values()}
    assert names == {"Other Tool Game"}  # foreign kept, orphan pruned
    assert not (grid / f"{orphan_aid}p.png").exists()  # art cleaned
    assert proton.get_compat_tool(str(cfg), orphan_aid) is None  # mapping cleaned
