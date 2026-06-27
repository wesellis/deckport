# Deploy hardening

A checklist for standing up `deckport.example` on a DigitalOcean droplet (or any
Ubuntu/Debian VPS) without leaving the obvious doors open. Work top to bottom;
each section is independent.

> **Why the risk is small to begin with.** The site is ~95% static files served
> by nginx. There are **no accounts, passwords, sessions, cookies, PII, or
> payments** — so most breach classes don't apply. The only dynamic surface is
> the votes API: parameterized SQL (no injection), regex-validated input, no
> secrets. This doc is about hardening the *server and the edge*, which is where
> real-world compromise actually happens.

## Architecture (what listens where)

```
            :443  ┌─────────── nginx (TLS, headers, rate-limit) ───────────┐
internet ─────────┤  /        → static files  (web/dist)                   │
            :80   │  /api/*   → proxy to 127.0.0.1:8000 (uvicorn, votes)    │
         (→ 443)  └────────────────────────────────────────────────────────┘
                      uvicorn binds ONLY to 127.0.0.1 — never public
```

The single rule that prevents most trouble: **only nginx is exposed (80/443).
The API binds to localhost and is reachable only through nginx.** Everything else
is closed at the firewall.

---

## 1. Users — never run anything as root

```bash
# a login user for you (deploys land here), and a no-login user for the service
adduser deploy
usermod -aG sudo deploy
adduser --system --group --no-create-home deckport
```

- You SSH in as `deploy`.
- The votes API runs as `deckport` (a system user with no shell, no home).
- nginx runs as its own `www-data`.

## 2. SSH — keys only, no root, fail2ban

Put your public key in `/home/deploy/.ssh/authorized_keys` first, confirm you can
log in, **then** lock it down in `/etc/ssh/sshd_config`:

```
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AllowUsers deploy
```

```bash
sudo systemctl restart ssh
sudo apt-get install -y fail2ban   # bans IPs that brute-force SSH; sane defaults
```

If you change the SSH port, update the firewall rule below to match.

## 3. Firewall — default-deny, three ports

```bash
sudo apt-get install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH        # or your custom SSH port
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Note what's **not** here: port 8000 (the API) is never opened. It's only reachable
via nginx on localhost.

## 4. Automatic security updates

```bash
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades   # enable security auto-updates
```

---

## 5. The votes API as a sandboxed service

Install it under `/opt/deckport/api` (owned by `deckport`) in its own venv:

```bash
sudo mkdir -p /opt/deckport/api /var/lib/deckport
sudo chown -R deckport:deckport /opt/deckport /var/lib/deckport
# (CI's deploy.yml rsyncs api/ here; or copy it manually the first time)
sudo -u deckport python3 -m venv /opt/deckport/api/.venv
sudo -u deckport /opt/deckport/api/.venv/bin/pip install -r /opt/deckport/api/requirements.txt
```

`/etc/systemd/system/deckport-api.service`:

```ini
[Unit]
Description=deckport votes API
After=network.target

[Service]
User=deckport
Group=deckport
WorkingDirectory=/opt/deckport/api
Environment=DECKPORT_DB=/var/lib/deckport/votes.db
# DECKPORT_STATIC_DIR is intentionally UNSET — nginx serves the static site.
ExecStart=/opt/deckport/api/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
Restart=on-failure

# --- sandboxing: the service can touch almost nothing ---
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6
RestrictNamespaces=true
LockPersonality=true
MemoryDenyWriteExecute=true
SystemCallFilter=@system-service
# the ONLY path it may write — the SQLite db lives here:
ReadWritePaths=/var/lib/deckport

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now deckport-api
sudo systemctl status deckport-api
```

`--host 127.0.0.1` is the load-bearing flag: the API is not reachable from the
internet, only proxied by nginx. The sandbox directives mean that even if the API
were somehow exploited, it can't write outside `/var/lib/deckport`, can't escalate
privileges, and can't open non-IP sockets.

---

## 6. nginx — TLS, security headers, rate limiting

Get a certificate first:

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
sudo certbot --nginx -d deckport.example -d www.deckport.example   # also sets up renewal
```

Rate-limit zones go in the `http {}` block (e.g. `/etc/nginx/nginx.conf`):

```nginx
# ~10 req/s/IP to the API, with a small burst; static files are unmetered.
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
# tighter bucket just for vote writes (POST), to blunt vote-stuffing.
limit_req_zone $binary_remote_addr zone=votes:10m rate=1r/s;
```

The site server block (`/etc/nginx/sites-available/deckport`):

```nginx
server {
    listen 443 ssl http2;
    server_name deckport.example www.deckport.example;

    ssl_certificate     /etc/letsencrypt/live/deckport.example/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/deckport.example/privkey.pem;

    root /var/www/deckport/site;     # web/dist lands here (deploy.yml rsyncs it)
    index index.html;

    # tiny request bodies only — votes are a few bytes; nothing is uploaded
    client_max_body_size 16k;

    # --- security headers ---
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header X-Frame-Options "DENY" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://*.steamgriddb.com; font-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'" always;

    # --- static site ---
    location / {
        try_files $uri $uri/ /404.html;
        # HTML must always revalidate, or a returning visitor paints the cached
        # OLD page (which references the OLD hashed CSS) before fetching the new
        # build — a visible flash of the previous theme. no-cache = "store but
        # revalidate every time" (cheap 304s when unchanged), so a fresh deploy
        # shows up immediately.
        add_header Cache-Control "no-cache" always;
    }
    location /_astro/ {            # hashed assets — cache hard (filename changes per build)
        expires 1y;
        add_header Cache-Control "public, immutable" always;
    }

    # --- votes API (the only dynamic path) ---
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        limit_req zone=votes burst=5 nodelay;     # extra brake on writes
        limit_except GET POST OPTIONS { deny all; }
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;   # the API rate-limits on this too
        proxy_read_timeout 10s;
    }
}

server {                          # port 80 → redirect to HTTPS (certbot also does this)
    listen 80;
    server_name deckport.example www.deckport.example;
    return 301 https://$host$request_uri;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/deckport /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Notes:
- The **CSP** is strict on scripts (`script-src 'self'` — the site ships no inline
  scripts, by design). `style-src` keeps `'unsafe-inline'` only because Astro
  components use inline `style=""` attributes; inline styles can't run code.
- `img-src` allows `*.steamgriddb.com` because recipe cards **hot-link** their
  banner art from the SteamGridDB CDN (referenced, never rehosted — see doc 06).
  If you ever stop showing card art, tighten this back to `'self' data:`.
- `connect-src 'self'` means the vote `fetch()` only talks to your own `/api`.
- `frame-ancestors 'none'` + `X-Frame-Options DENY` stop clickjacking.
- The double rate-limit on `/api` is the main defense against vote-stuffing —
  see also the API's own in-process IP throttle (40 writes/min).

Verify the headers with `curl -I https://deckport.example` or
[securityheaders.com](https://securityheaders.com).

---

## 7. The deploy pipeline's secrets

`deploy.yml` (gated on the `DEPLOY_ENABLED` repo variable) needs these GitHub
**secrets**. They are the keys to the box — treat them accordingly:

| secret | what it is | hardening |
|--------|-----------|-----------|
| `DEPLOY_SSH_KEY` | private key for `deploy@droplet` | a **dedicated** deploy key, not your personal key; rotate if leaked |
| `DEPLOY_HOST` / `DEPLOY_USER` | the droplet + `deploy` | — |
| `DEPLOY_SITE_PATH` | e.g. `/var/www/deckport/site` | owned by `deploy`, served by nginx |
| `DEPLOY_API_PATH` | e.g. `/opt/deckport/api` | — |
| `DEPLOY_RESTART_CMD` | restarts the API | scope it via sudoers (below) |

Don't give the deploy user blanket `sudo`. Limit it to exactly the restart:

```
# /etc/sudoers.d/deckport   (visudo -f)
deploy ALL=(root) NOPASSWD: /bin/systemctl restart deckport-api
```

Then `DEPLOY_RESTART_CMD = "sudo systemctl restart deckport-api"`.

## 8. Dependency hygiene

- Turn on **Dependabot** (`.github/dependabot.yml`) for `pip` (api + tooling) and
  `npm` (web). FastAPI/uvicorn/starlette and Astro all ship security fixes.
- CI already runs the test suite on every PR, so a Dependabot bump that breaks
  something is caught before merge.

## 9. Backups & data

- `votes.db` is **derived signal**, not the source of truth (recipes live in git),
  so losing it only resets vote counts. Still, a nightly copy is cheap:
  `sqlite3 /var/lib/deckport/votes.db ".backup /var/backups/votes-$(date +\%F).db"`
  via cron, keep ~7.
- There is **nothing sensitive** in the DB — anonymous voter ids and IP strings
  only. If you'd rather not retain IPs, drop the `ip` column; the rate-limit still
  works off nginx + the in-process throttle.

---

## Go-live checklist

- [ ] SSH: root login off, password auth off, `fail2ban` running
- [ ] `ufw` enabled, only SSH/80/443 open, **port 8000 not exposed**
- [ ] API runs as the `deckport` user under systemd, bound to `127.0.0.1`, sandboxed
- [ ] `unattended-upgrades` enabled
- [ ] TLS via certbot; HTTP redirects to HTTPS; auto-renew tested (`certbot renew --dry-run`)
- [ ] Security headers + CSP present (check securityheaders.com → aim for A)
- [ ] `/api` rate-limited at nginx; `client_max_body_size` small
- [ ] Deploy user's sudo limited to the one restart command; deploy key is dedicated
- [ ] Dependabot on for pip + npm
- [ ] `votes.db` backup cron in place

Done all that and the honest answer to "will it get hacked?" is: not through this
app — the remaining risk is a future CVE in a dependency, which Dependabot + patching
keeps on top of.
