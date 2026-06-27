# deckport vote API

A tiny FastAPI + SQLite service backing the anonymous **"does it run on your
Deck?"** thumbs up/down on each recipe page. It is the first piece of the
community layer (doc 07). The recipe book stays in git (decision D2) — votes are
derived signal, rebuildable and never the source of truth for a recipe's status.

## Endpoints

| method | path                  | purpose                                   |
|--------|-----------------------|-------------------------------------------|
| GET    | `/api/health`         | liveness                                  |
| GET    | `/api/votes/{slug}`   | `{ slug, up, down }`                       |
| POST   | `/api/votes/{slug}`   | body `{ vote: "up"\|"down"\|"none", voter }` → updated counts |

One row per `(slug, voter)` — a visitor can switch their vote or undo it
(`"none"`), but not stack it. `voter` is an anonymous id the browser keeps in
`localStorage`. Writes are IP rate-limited (40 / minute) to blunt casual spam.

## Run locally (single process, mirrors production)

Serve the built site *and* the API from one process so `/api` is same-origin,
exactly like the droplet:

```bash
cd web && npm run build && cd ../api
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux
DECKPORT_STATIC_DIR=../web/dist uvicorn app:app --port 8000
# open http://127.0.0.1:8000/
```

For a split dev setup (Astro on :4321, API on :8000) build the site with
`PUBLIC_API_BASE=http://127.0.0.1:8000/api`; CORS is open so cross-origin works.

## Deploy on the DigitalOcean droplet

Same shape as g8kepr: **nginx serves the static site and proxies `/api`** to
this uvicorn process. Then `DECKPORT_STATIC_DIR` stays unset (nginx owns static).

1. `scp web/dist` to e.g. `/var/www/deckport/site`; point an nginx `root` at it.
2. Run the API under a process manager (systemd or PM2):
   `uvicorn app:app --host 127.0.0.1 --port 8000`
3. nginx location blocks:
   ```nginx
   location /api/ { proxy_pass http://127.0.0.1:8000; }
   location /    { root /var/www/deckport/site; try_files $uri $uri/ /404.html; }
   ```

## Config

| env                  | default        | meaning                                  |
|----------------------|----------------|------------------------------------------|
| `DECKPORT_DB`        | `./votes.db`   | SQLite file path                         |
| `DECKPORT_STATIC_DIR`| _(unset)_      | if set, also serve this dir as the site  |

`votes.db` is gitignored. Back it up if you care about the counts; it's safe to
delete to reset all votes to zero.
