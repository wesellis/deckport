"""Tests for the Proton CompatToolMapping writer (config.vdf)."""
import os

from deckport import proton, textvdf


def test_set_on_fresh_file_creates_tree(tmp_path):
    cfg = tmp_path / "config" / "config.vdf"
    assert proton.set_compat_tool(str(cfg), 3858907385, "proton_experimental")
    assert proton.get_compat_tool(str(cfg), 3858907385) == "proton_experimental"
    # full canonical path exists
    root = textvdf.load_file(str(cfg))
    assert "CompatToolMapping" in root["InstallConfigStore"]["Software"]["Valve"]["Steam"]


def test_set_preserves_existing_content_and_backs_up(tmp_path):
    cfg = tmp_path / "config.vdf"
    existing = {
        "InstallConfigStore": {
            "Software": {"Valve": {"Steam": {"SomeOtherSetting": "keep-me"}}},
            "AnotherTopKey": "also-keep",
        }
    }
    textvdf.save_file(str(cfg), existing)

    proton.set_compat_tool(str(cfg), 111, "GE-Proton9-20", priority=250)

    root = textvdf.load_file(str(cfg))
    steam = root["InstallConfigStore"]["Software"]["Valve"]["Steam"]
    assert steam["SomeOtherSetting"] == "keep-me"  # untouched
    assert root["InstallConfigStore"]["AnotherTopKey"] == "also-keep"
    assert steam["CompatToolMapping"]["111"]["name"] == "GE-Proton9-20"
    assert os.path.exists(str(cfg) + ".deckport.bak")  # backup written


def test_case_insensitive_navigation(tmp_path):
    cfg = tmp_path / "config.vdf"
    # Steam has shipped lowercase 'valve'/'steam' — we must reuse, not duplicate.
    textvdf.save_file(str(cfg), {"InstallConfigStore": {"software": {"valve": {"steam": {}}}}})
    proton.set_compat_tool(str(cfg), 222, "proton_9")
    root = textvdf.load_file(str(cfg))
    sw = root["InstallConfigStore"]["software"]
    assert "valve" in sw and "Valve" not in sw  # reused the existing lowercase block
    assert sw["valve"]["steam"]["CompatToolMapping"]["222"]["name"] == "proton_9"


def test_remove(tmp_path):
    cfg = tmp_path / "config.vdf"
    proton.set_compat_tool(str(cfg), 333, "proton_experimental")
    assert proton.remove_compat_tool(str(cfg), 333)
    assert proton.get_compat_tool(str(cfg), 333) is None
    assert proton.remove_compat_tool(str(cfg), 333) is False  # already gone


def test_set_empty_tool_is_noop(tmp_path):
    cfg = tmp_path / "config.vdf"
    assert proton.set_compat_tool(str(cfg), 444, "") is False
    assert not cfg.exists()


def test_set_with_bare_filename_no_dir(tmp_path, monkeypatch):
    # os.path.dirname("config.vdf") == "" -> must not call makedirs("") (WinError 3).
    monkeypatch.chdir(tmp_path)
    assert proton.set_compat_tool("config.vdf", 555, "proton_experimental")
    assert proton.get_compat_tool("config.vdf", 555) == "proton_experimental"


# --- normalize_proton: human recipe strings -> valid CompatToolMapping names ---

def test_normalize_valve_human_strings():
    assert proton.normalize_proton("Proton 7.0-6")[0] == "proton_7"
    assert proton.normalize_proton("Proton 9.0-4")[0] == "proton_9"
    assert proton.normalize_proton("Proton 8")[0] == "proton_8"
    assert proton.normalize_proton("Proton 6.3")[0] == "proton_63"
    assert proton.normalize_proton("Proton 4.2-9")[0] == "proton_42"
    assert proton.normalize_proton("Proton Experimental")[0] == "proton_experimental"
    assert proton.normalize_proton("proton_experimental")[0] == "proton_experimental"


def test_normalize_specific_ge_build_passthrough():
    # An exact GE folder name is used as-is.
    name, _ = proton.normalize_proton("GE-Proton8-22", installed=["GE-Proton8-22"])
    assert name == "GE-Proton8-22"


def test_normalize_bare_ge_resolves_to_newest_installed():
    name, note = proton.normalize_proton(
        "GE-Proton", installed=["GE-Proton8-32", "GE-Proton9-20", "SomeOther"]
    )
    assert name == "GE-Proton9-20"
    assert "GE-Proton9-20" in note


def test_normalize_bare_ge_without_install_returns_none_and_warns():
    name, note = proton.normalize_proton("GE-Proton", installed=[])
    assert name is None
    assert "ProtonUp-Qt" in note


def test_normalize_empty_is_none():
    assert proton.normalize_proton("")[0] is None
