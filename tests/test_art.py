"""Tests for the SteamGridDB artwork fetcher (pure logic + a fake client).

No network: the fetch test injects a fake client, so we verify the orchestration
(match -> per-slot pick -> generic file written into .deckport-art/) deterministically.
"""

from deckport.appid import ART_SLOTS as IMPORTER_SLOTS
from deckport.artwork import ART_DIR
from deckport_art.fetch import fetch_into
from deckport_art.search import SLOT_QUERY, best_match, ext_for, normalize


# -- pure logic --------------------------------------------------------------

def test_slots_agree_with_importer():
    # The fetcher's slots must match the importer's grid-naming slots exactly,
    # or art would be written that the Deck never renames.
    assert set(SLOT_QUERY) == set(IMPORTER_SLOTS)


def test_normalize():
    assert normalize("Celeste") == "celeste"
    assert normalize("Hollow Knight: Silksong") == "hollow knight silksong"
    assert normalize("DOOM (1993) Remastered Edition") == "doom 1993"


def test_best_match_exact_and_fuzzy():
    cands = [{"id": 1, "name": "Celestium"}, {"id": 2, "name": "Celeste"}]
    assert best_match("Celeste", cands)["id"] == 2  # exact normalized wins
    assert best_match("celeste", [{"id": 9, "name": "Celeste: Farewell"}])["id"] == 9  # fuzzy
    assert best_match("Totally Unrelated XYZ", [{"id": 1, "name": "Celeste"}]) is None
    assert best_match("anything", []) is None


def test_ext_for():
    assert ext_for("https://x/y/z.png") == "png"
    assert ext_for("https://x/y/z.jpg") == "jpg"
    assert ext_for("https://x/y/z.jpeg") == "jpg"
    assert ext_for("https://cdn/abc?token=1", mime="image/png") == "png"  # mime wins
    assert ext_for("https://cdn/abc?token=1") == "png"  # safe default


# -- orchestration with a fake client ---------------------------------------

class FakeClient:
    """Stand-in for SteamGridDB with canned data and no network."""

    def __init__(self, candidates, art):
        self._candidates = candidates
        self._art = art  # slot -> list[dict]
        self.downloads = []

    def search(self, term):
        return self._candidates

    def artwork(self, game_id, slot, dimensions=None, limit=20):
        return self._art.get(slot, [])

    def download(self, url):
        self.downloads.append(url)
        return b"IMGDATA:" + url.encode()


def _client_with_all_art():
    return FakeClient(
        candidates=[{"id": 42, "name": "Cool Game"}],
        art={
            "grid": [{"url": "https://sgdb/grid.png", "mime": "image/png"}],
            "hero": [{"url": "https://sgdb/hero.jpg", "mime": "image/jpeg"}],
            "logo": [{"url": "https://sgdb/logo.png", "mime": "image/png"}],
            "icon": [{"url": "https://sgdb/icon.png", "mime": "image/png"}],
        },
    )


def test_fetch_writes_generic_files(tmp_path):
    client = _client_with_all_art()
    res = fetch_into(client, "Cool Game", str(tmp_path))
    assert res.ok and res.game["id"] == 42
    art_dir = tmp_path / ART_DIR
    # cover + grid both come from the "grid" endpoint (portrait vs landscape dims)
    assert (art_dir / "cover.png").read_bytes().startswith(b"IMGDATA:")
    assert (art_dir / "grid.png").exists()
    assert (art_dir / "hero.jpg").exists()
    assert (art_dir / "logo.png").exists()
    assert (art_dir / "icon.png").exists()
    assert set(res.written) == set(SLOT_QUERY)


def test_dry_run_downloads_nothing(tmp_path):
    client = _client_with_all_art()
    res = fetch_into(client, "Cool Game", str(tmp_path), dry_run=True)
    assert res.written  # it reports what it *would* write
    assert client.downloads == []
    assert not (tmp_path / ART_DIR).exists()


def test_missing_slots_and_no_match(tmp_path):
    partial = FakeClient(
        candidates=[{"id": 7, "name": "Cool Game"}],
        art={"grid": [{"url": "https://sgdb/g.jpg", "mime": "image/jpeg"}]},  # only grids
    )
    res = fetch_into(partial, "Cool Game", str(tmp_path))
    assert "hero" in res.missing and "logo" in res.missing and "icon" in res.missing
    assert "cover" in res.written and "grid" in res.written

    nomatch = FakeClient(candidates=[{"id": 1, "name": "Something Else Entirely"}], art={})
    res2 = fetch_into(nomatch, "Cool Game", str(tmp_path))
    assert res2.game is None and not res2.ok


def test_switching_extension_clears_stale(tmp_path):
    art_dir = tmp_path / ART_DIR
    art_dir.mkdir()
    (art_dir / "cover.jpg").write_bytes(b"old")  # stale jpg from a prior run
    client = FakeClient(
        candidates=[{"id": 1, "name": "G"}],
        art={"grid": [{"url": "https://sgdb/new.png", "mime": "image/png"}]},
    )
    fetch_into(client, "G", str(tmp_path), slots=["cover"])
    assert not (art_dir / "cover.jpg").exists()  # stale cleared
    assert (art_dir / "cover.png").exists()
