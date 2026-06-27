"""Tests for deterministic app IDs and the artwork filename mapping."""
import pytest

from deckport.appid import art_filename, shortcut_appid, to_signed32, to_unsigned32


def test_appid_is_deterministic_and_high_bit():
    a = shortcut_appid('"/games/x/x.x86_64"', "X")
    b = shortcut_appid('"/games/x/x.x86_64"', "X")
    assert a == b  # deterministic
    assert a & 0x80000000  # in the non-Steam reserved range
    assert 0 <= a <= 0xFFFFFFFF


def test_appid_changes_with_inputs():
    assert shortcut_appid('"/a/a"', "A") != shortcut_appid('"/a/a"', "B")
    assert shortcut_appid('"/a/a"', "A") != shortcut_appid('"/b/b"', "A")


def test_signed_unsigned_inverse():
    aid = shortcut_appid('"/q"', "Q")
    assert to_unsigned32(to_signed32(aid)) == aid
    assert to_signed32(aid) < 0  # high bit set -> negative when signed


def test_art_filename_mapping():
    aid = 3580912219  # example from the README
    assert art_filename(aid, "cover", "jpg") == "3580912219p.jpg"
    assert art_filename(aid, "grid", "jpg") == "3580912219.jpg"
    assert art_filename(aid, "hero", "jpg") == "3580912219_hero.jpg"
    assert art_filename(aid, "logo", "png") == "3580912219_logo.png"
    assert art_filename(aid, "icon", "png") == "3580912219_icon.png"
    # leading dot on ext is tolerated
    assert art_filename(aid, "grid", ".png") == "3580912219.png"


def test_art_filename_normalizes_signed_appid():
    aid = shortcut_appid('"/z"', "Z")
    assert art_filename(to_signed32(aid), "cover", "jpg") == f"{aid}p.jpg"


def test_unknown_slot_raises():
    with pytest.raises(KeyError):
        art_filename(123, "banner", "jpg")
