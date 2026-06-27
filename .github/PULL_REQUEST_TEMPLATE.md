<!-- For recipe PRs, check the recipe boxes. For code PRs, the code boxes. -->

## What does this change?



## Type
- [ ] New / updated recipe
- [ ] Code (importer / tools)
- [ ] Docs
- [ ] Website

## Recipe PRs
- [ ] Filename matches `game.slug`
- [ ] `status` is honest (`working` includes a real `verified_on` SteamOS build)
- [ ] No game files, acquisition links, or DRM-circumvention content
- [ ] Validated locally (`deckport recipe validate recipes/<slug>.toml`)

## Code PRs
- [ ] Deck-side code stays pure standard library
- [ ] Tests added/updated for VDF or recipe changes
- [ ] Lint + `pytest` pass locally
- [ ] `CHANGELOG.md` updated under "Unreleased"
- [ ] Docs updated if behavior changed
