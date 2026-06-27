"""Tests for the binary shortcuts.vdf reader/writer.

The non-negotiables: round-trip equality, byte-for-byte idempotent rewrites
(so we never corrupt a user's existing shortcuts), and correct handling of the
high-bit app IDs that non-Steam shortcuts use (the >2^31 regression).
"""
from deckport import vdf
from deckport.appid import shortcut_appid, to_signed32, to_unsigned32


def _sample() -> dict:
    return {
        "0": {
            "appid": to_signed32(shortcut_appid('"/games/a/a.x86_64"', "Game A")),
            "AppName": "Game A",
            "Exe": '"/games/a/a.x86_64"',
            "StartDir": '"/games/a/"',
            "IsHidden": 0,
            "AllowOverlay": 1,
            "LastPlayTime": 0,
            "tags": {"0": "Ported Games"},
        },
        "1": {
            "appid": to_signed32(shortcut_appid('"/games/b/b"', "Game B")),
            "AppName": "Game B — accented ✓ name",
            "Exe": '"/games/b/b"',
            "StartDir": '"/games/b/"',
            "tags": {},
        },
    }


def test_round_trip_equal():
    m = _sample()
    assert vdf.loads(vdf.dumps(m)) == m


def test_rewrite_is_byte_identical_idempotent():
    m = _sample()
    once = vdf.dumps(m)
    twice = vdf.dumps(vdf.loads(once))
    assert once == twice  # load->save must not drift a single byte


def test_high_bit_appid_round_trips():
    # Non-Steam app IDs have the high bit set (>2^31); the VDF stores them signed.
    aid_unsigned = shortcut_appid('"/x/y.x86_64"', "Y")
    assert aid_unsigned & 0x80000000  # high bit set
    m = {"0": {"appid": to_signed32(aid_unsigned), "AppName": "Y"}}
    back = vdf.loads(vdf.dumps(m))
    assert to_unsigned32(back["0"]["appid"]) == aid_unsigned


def test_empty_and_missing():
    assert vdf.loads(b"") == {}
    assert vdf.loads(vdf.dumps({})) == {}


def test_all_value_types():
    m = {"0": {"AppName": "S", "IsHidden": 0, "Devkit": 1, "nested": {"0": "tag"}}}
    back = vdf.loads(vdf.dumps(m))
    assert back == m
    assert isinstance(back["0"]["IsHidden"], int)
    assert isinstance(back["0"]["nested"], dict)


def test_load_save_file_round_trip(tmp_path):
    p = tmp_path / "shortcuts.vdf"
    m = _sample()
    vdf.save_shortcuts(str(p), m)
    assert vdf.load_shortcuts(str(p)) == m
    assert vdf.load_shortcuts(str(tmp_path / "missing.vdf")) == {}
