"""Tests for binary detection and folder-name cleanup."""

from deckport.detect import clean_name, find_binary, is_elf, score_candidate

ELF = b"\x7fELF" + b"\x00" * 4096


def _write(path, data=ELF):
    with open(path, "wb") as f:
        f.write(data)


def test_clean_name():
    assert clean_name("Super Mario Bros. Remastered (1.0.1) (Linux)") == "Super Mario Bros. Remastered"
    assert clean_name("MiniTroid_v1.2.3") == "MiniTroid"
    assert clean_name("Cool_Game") == "Cool Game"


def test_is_elf(tmp_path):
    good = tmp_path / "a.x86_64"
    bad = tmp_path / "readme.txt"
    _write(good)
    _write(bad, b"not an elf")
    assert is_elf(str(good))
    assert not is_elf(str(bad))
    assert not is_elf(str(tmp_path / "missing"))


def test_godot_export_wins(tmp_path):
    d = tmp_path / "My Game (Linux)"
    d.mkdir()
    _write(d / "My Game.x86_64")
    _write(d / "libgodot.so")  # shared lib must be rejected
    _write(d / "data.bin", b"\x00\x00")  # not an ELF
    binary = find_binary(str(d))
    assert binary is not None and binary.endswith("My Game.x86_64")


def test_shared_objects_rejected(tmp_path):
    d = tmp_path / "only-so"
    d.mkdir()
    _write(d / "libfoo.so")
    assert find_binary(str(d)) is None


def test_no_executable(tmp_path):
    d = tmp_path / "no-bin"
    d.mkdir()
    _write(d / "save.dat", b"data")
    assert find_binary(str(d)) is None


def test_bare_elf_beats_so(tmp_path):
    d = tmp_path / "x"
    d.mkdir()
    _write(d / "game")  # bare-name ELF
    _write(d / "lib.so")
    assert score_candidate(str(d), "game") > score_candidate(str(d), "lib.so")
