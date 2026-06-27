# Security policy

deckport is a small side project, maintained best-effort. We still take security
seriously — here's the posture and how to report problems.

## Reporting a vulnerability

Please **don't** open a public issue for a security problem. Instead:

- Open a [GitHub private security advisory](https://github.com/wesellis/deckport/security/advisories/new), or
- email **wes@wesellis.com**.

Include what you found, how to reproduce it, and the impact. We'll acknowledge and
work a fix; there's no bounty, just gratitude and credit if you'd like it.

## What's in scope

- The website (`web/`) and the votes API (`api/`).
- The importer (`deckport.py` / `src/deckport/`) and PC-side tools (`tools/`).
- The recipe validation / content-line enforcement.

**Out of scope:** the games themselves. deckport never hosts game files, ROMs, or
download links — recipes describe *configuration only*, and the recipe validator
rejects links to game-file sources (the "content line"). A recipe that tries to
smuggle one in is a content violation, handled by CI + review, not a security bug.

## Security model (why the surface is small)

- **No accounts, passwords, sessions, cookies, PII, or payments.** Most breach
  classes simply don't apply.
- The site is **static** HTML/CSS/JS; the only dynamic path is anonymous votes.
- The votes API uses **parameterized SQL** (no injection), **regex-validated**
  input, an in-process write rate-limit, and holds no secrets.
- Community-supplied links are **allowlisted to `http(s)`** before they're ever
  put in an `href` (no `javascript:` URLs), at both the render layer and in CI.
- The shipped site uses a strict **Content-Security-Policy** (no inline scripts).

## Deploying securely

If you're standing up an instance, follow **[docs/DEPLOY_HARDENING.md](docs/DEPLOY_HARDENING.md)**
— firewall, keys-only SSH, a sandboxed non-root systemd service bound to
localhost, TLS, security headers + CSP, and `/api` rate-limiting. It ends with a
go-live checklist.

## Dependencies

Enable Dependabot for `pip` (api + tools) and `npm` (web). CI runs the full test
suite on every PR, so a dependency bump that breaks something is caught before it
merges.
