# deckport-recipes

Community recipes that tell [deckport](../) how to get a game running on a
Steam Deck — which binary to launch, what data files it needs, which Proton
version and winetricks for Windows titles, and where to find its artwork.

One TOML file per game in `recipes/`. The format is in
[RECIPE_FORMAT.md](RECIPE_FORMAT.md); copy `recipes/_template.toml` to start.

## Status is the whole point

Every recipe carries a `status`. Seed entries are `unverified` or `needs-test`
because no one has run them on a real Deck yet. If you confirm one works,
bump it to `working`, fill in `verified_on` with your SteamOS build, and open
a PR. If it's broken, set `borked` and say why — a known dead end saves the
next person an evening.

## Seeds

| game | type | engine | status |
|------|------|--------|--------|
| Super Mario Bros. Remastered | native | godot | needs-test |
| Minitroid | native | love | unverified |

## Contributing

1. Get a game running on your Deck.
2. Copy `recipes/_template.toml` to `recipes/<slug>.toml` and fill it in.
3. Set an honest `status` and your `contributor` handle.
4. Open a pull request.

Recipes describe how to **configure** a game (binary, Proton, winetricks,
launch options). They never include game files, links to obtain them, or
anything about defeating copy protection.
