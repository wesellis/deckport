# Governance

deckport is designed to be **community-run with a near-absent owner.** The
recipe book is a folder of TOML in git (decision D2), so the day-to-day work —
adding and fixing recipes — is done by contributors via pull requests, and the
machine does most of the reviewing. This document says who can do what and how
you get more rights.

## Roles

| role | can | how you get it |
|------|-----|----------------|
| **Contributor** | open issues + PRs (recipes or code) | just do it — no account beyond GitHub |
| **Trusted contributor** | merge recipe PRs that pass CI | **3+ merged, good-quality recipe PRs**, then ask an admin (or get nominated) |
| **Maintainer** | merge code PRs, manage labels/releases | sustained code contributions + an admin invite |
| **Owner/admin** | repo settings, grant roles, the legal backstop | the project owner |

The goal is for **trusted contributors to run the recipe book** so the owner's
role shrinks to "occasionally add a trusted contributor." The owner stays the
legal backstop because they host the domain (see "What can't be delegated").

## How a recipe gets in (no owner required)

1. Someone opens a PR (or fills the recipe-request issue / future web form,
   which opens a PR for them).
2. **CI reviews it automatically** — see the gate below. A failing PR can't be
   merged.
3. Any **trusted contributor** (not necessarily the owner) reviews and merges.
4. On merge, the site rebuilds and deploys (see `deploy.yml`). Live, hands-off.

## The automated gate (the "robot reviewer")

Every recipe PR must pass, with **no human needed to catch these**:

- **Shape + enums** — valid TOML, required fields, `type`/`engine`/`status` enums
  (`scripts/validate_recipes.py` + `schema.json`).
- **The honest rule** — `status = "working"` is rejected without `verified_on`;
  `borked` is rejected without `caveats`; a Proton title needs `proton.version`.
- **Slug** — `game.slug` equals the filename.
- **The content line** — a denylist (`deckport.recipe.FORBIDDEN_TOKENS`) rejects
  any link to ROM/abandonware/warez/torrent sources or DRM-circumvention. This is
  the safety gate that makes unattended community submissions OK to merge.
- **Tests + lint stay green** (`ci.yml`).

Because the gate enforces the content line mechanically, a trusted contributor
merging a recipe doesn't have to be a lawyer — the bad stuff bounces before
review.

## Optional: zero-human merging

For maximum hands-off, enable branch automation so a recipe PR **auto-merges once
CI is green and it has N approvals** from trusted contributors (GitHub branch
rules + an auto-merge action). The owner never has to touch it. Start with human
merge; turn this on once there's a reliable group of trusted contributors.

## What can't be delegated

The owner hosts the domain and droplet, so **they are the legal operator** no
matter who writes the recipes. That's why the content line is non-negotiable and
enforced by CI: by never linking to game files, there's nothing infringing
hosted, which keeps that residual responsibility small. A rightsholder takedown,
if one ever comes, goes to the owner — the denylist exists to make that vanishingly unlikely.

## Becoming a trusted contributor

Open 3+ recipe PRs that pass CI and reflect the honest-status discipline (you
actually checked what you claim). Then open an issue titled "merge-rights
request" linking them, or wait to be nominated. Admins grant the role via repo
settings (Triage/Write as appropriate).

## Removing rights

Rights can be revoked for repeatedly merging recipes that violate the content
line or the honest-status rule. The bar is intentionally low here — trust in the
corpus is the whole product.
