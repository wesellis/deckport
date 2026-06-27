"""deckport vote API — anonymous "does it work on your Deck?" thumbs up/down.

A deliberately small service: FastAPI + stdlib sqlite3, no ORM. It stores one
row per (recipe slug, anonymous voter id) so a visitor can switch their vote but
not stack it. Counts are aggregated on read.

This is the *community* layer (doc 07). The recipe book itself stays in git
(decision D2) — votes are derived, throwaway-rebuildable signal, never the
source of truth for whether a recipe is "working".

Run locally (serving the built site too, so /api is same-origin like prod):

    pip install -r requirements.txt
    DECKPORT_STATIC_DIR=../web/dist uvicorn app:app --port 8000

In production on the droplet: nginx serves web/dist and proxies /api/* to this
uvicorn process (same pattern as g8kepr). Then DECKPORT_STATIC_DIR is unset.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

DB_PATH = os.environ.get("DECKPORT_DB", os.path.join(os.path.dirname(__file__), "votes.db"))
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
VOTER_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

# Simple in-memory write throttle: max N writes per IP per window. Resets on
# restart; good enough to blunt casual spam on a small community site.
_WRITE_WINDOW_S = 60
_WRITE_MAX = 40
_write_log: dict[str, deque] = defaultdict(deque)

# Privacy: we never persist a raw client IP. The throttle uses it in memory only;
# the DB row stores a salted hash so abuse can still be correlated without
# keeping PII. Set DECKPORT_IP_SALT in prod so hashes aren't guessable.
_IP_SALT = os.environ.get("DECKPORT_IP_SALT", "deckport-votes-salt")


def hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{_IP_SALT}|{ip}".encode("utf-8")).hexdigest()[:32]


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(db()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS votes (
                slug    TEXT NOT NULL,
                voter   TEXT NOT NULL,
                vote    INTEGER NOT NULL,   -- +1 up, -1 down
                ip      TEXT,
                updated REAL NOT NULL,
                PRIMARY KEY (slug, voter)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_votes_slug ON votes(slug)")
        conn.commit()


def counts(conn: sqlite3.Connection, slug: str) -> dict:
    row = conn.execute(
        "SELECT "
        "COALESCE(SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END),0) AS up, "
        "COALESCE(SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END),0) AS down "
        "FROM votes WHERE slug=?",
        (slug,),
    ).fetchone()
    return {"up": int(row["up"]), "down": int(row["down"])}


def throttle(ip: str) -> None:
    now = time.time()
    q = _write_log[ip]
    while q and now - q[0] > _WRITE_WINDOW_S:
        q.popleft()
    if len(q) >= _WRITE_MAX:
        raise HTTPException(status_code=429, detail="slow down")
    q.append(now)


class VoteIn(BaseModel):
    vote: str  # "up" | "down" | "none"
    voter: str


@asynccontextmanager
async def _lifespan(app: FastAPI):
    init_db()  # create the table/index on startup (modern lifespan, not on_event)
    yield


app = FastAPI(title="deckport vote API", version="0.1.0", lifespan=_lifespan)

# Votes aren't sensitive and carry no cookies/credentials, so an open CORS
# policy is safe and keeps local cross-origin dev painless. Set
# DECKPORT_CORS_ORIGINS (comma-separated) in prod to lock it to your domain.
_cors = os.environ.get("DECKPORT_CORS_ORIGINS", "*").strip()
_allow_origins = ["*"] if _cors in ("", "*") else [o.strip() for o in _cors.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/votes")
def get_votes_batch(slugs: str = "") -> JSONResponse:
    """Counts for many recipes at once: /api/votes?slugs=a,b,c -> {a:{up,down},...}.

    Lets a list/grid of cards fetch every count in a single request.
    """
    wanted = [s for s in slugs.split(",") if s][:200]
    out: dict[str, dict] = {}
    with closing(db()) as conn:
        for s in wanted:
            if SLUG_RE.match(s):
                out[s] = counts(conn, s)
    return JSONResponse(out)


@app.get("/api/votes/{slug}")
def get_votes(slug: str) -> JSONResponse:
    if not SLUG_RE.match(slug):
        raise HTTPException(status_code=400, detail="bad slug")
    with closing(db()) as conn:
        return JSONResponse({"slug": slug, **counts(conn, slug)})


@app.post("/api/votes/{slug}")
def cast_vote(slug: str, body: VoteIn, request: Request) -> JSONResponse:
    if not SLUG_RE.match(slug):
        raise HTTPException(status_code=400, detail="bad slug")
    if not VOTER_RE.match(body.voter):
        raise HTTPException(status_code=400, detail="bad voter id")
    if body.vote not in ("up", "down", "none"):
        raise HTTPException(status_code=400, detail="vote must be up, down or none")

    ip = (request.client.host if request.client else "") or "unknown"
    throttle(ip)

    with closing(db()) as conn:
        if body.vote == "none":
            conn.execute("DELETE FROM votes WHERE slug=? AND voter=?", (slug, body.voter))
        else:
            v = 1 if body.vote == "up" else -1
            conn.execute(
                "INSERT INTO votes (slug, voter, vote, ip, updated) VALUES (?,?,?,?,?) "
                "ON CONFLICT(slug, voter) DO UPDATE SET vote=excluded.vote, ip=excluded.ip, updated=excluded.updated",
                (slug, body.voter, v, hash_ip(ip), time.time()),
            )
        conn.commit()
        return JSONResponse({"slug": slug, "you": body.vote, **counts(conn, slug)})


# Optionally serve the built static site too, so a single local process mirrors
# production (/api same-origin). In prod, nginx serves the static files instead
# and this stays unset.
_static = os.environ.get("DECKPORT_STATIC_DIR")
if _static and os.path.isdir(_static):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_static, html=True), name="site")
