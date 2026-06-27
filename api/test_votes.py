"""Tests for the votes API. Run from the api/ dir: ``pytest`` (needs fastapi+httpx).

Kept out of the main package test suite (which is stdlib/Deck-focused); CI runs
this in its own job with the API's own dependencies.
"""
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DECKPORT_DB", str(tmp_path / "votes.db"))
    import app as app_module
    importlib.reload(app_module)  # re-read DB_PATH from the patched env
    with TestClient(app_module.app) as c:  # context -> lifespan runs init_db()
        yield c


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_empty_counts(client):
    assert client.get("/api/votes/minitroid").json() == {"slug": "minitroid", "up": 0, "down": 0}


def test_vote_up_then_switch_does_not_stack(client):
    r = client.post("/api/votes/minitroid", json={"vote": "up", "voter": "voter-abc12345"})
    assert r.json() == {"slug": "minitroid", "you": "up", "up": 1, "down": 0}
    r = client.post("/api/votes/minitroid", json={"vote": "down", "voter": "voter-abc12345"})
    assert r.json() == {"slug": "minitroid", "you": "down", "up": 0, "down": 1}  # switched, not stacked


def test_two_voters_and_undo(client):
    client.post("/api/votes/celeste", json={"vote": "up", "voter": "voter-aaaaaaaa"})
    client.post("/api/votes/celeste", json={"vote": "up", "voter": "voter-bbbbbbbb"})
    assert client.get("/api/votes/celeste").json() == {"slug": "celeste", "up": 2, "down": 0}
    client.post("/api/votes/celeste", json={"vote": "none", "voter": "voter-aaaaaaaa"})  # undo
    assert client.get("/api/votes/celeste").json() == {"slug": "celeste", "up": 1, "down": 0}


def test_batch(client):
    client.post("/api/votes/a-game", json={"vote": "up", "voter": "voter-12345678"})
    out = client.get("/api/votes?slugs=a-game,b-game").json()
    assert out == {"a-game": {"up": 1, "down": 0}, "b-game": {"up": 0, "down": 0}}


@pytest.mark.parametrize(
    "slug,voter,vote,code",
    [
        ("Bad_Slug", "voter-12345678", "up", 400),  # uppercase/underscore slug
        ("ok-slug", "short", "up", 400),  # voter too short
        ("ok-slug", "voter-12345678", "sideways", 400),  # bad vote value
    ],
)
def test_validation_rejects_bad_input(client, slug, voter, vote, code):
    assert client.post(f"/api/votes/{slug}", json={"vote": vote, "voter": voter}).status_code == code


def test_bad_slug_on_get(client):
    assert client.get("/api/votes/Bad_Slug!").status_code == 400
