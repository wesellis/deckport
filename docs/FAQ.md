# FAQ

## What is deckport?

A tool that gets a portable Linux game (Godot, LÖVE, generic ELF) onto a Steam
Deck as a non-Steam shortcut, dressed in SteamGridDB artwork, ready in Game Mode.
A PC side fetches art and pushes the game; the Deck side imports it. The Deck
importer is one pure-Python-standard-library file — nothing to install.

## Do I have to install anything on the Deck?

No. The Deck side is a single `deckport.py` you drop in your home folder and run
with the Python that already ships on SteamOS. It uses only the standard library
so it works on the read-only SteamOS root. The PC-side tools (`deckport-art`,
`deckport-push`, `deckport-recipe`) are a normal `pip install`.

## Is this safe? Will it touch my Steam games or settings?

It only adds **non-Steam shortcuts** and copies artwork into Steam's `grid/`
folder. It never modifies your installed Steam games. Before changing
`shortcuts.vdf` (or `config.vdf` for Proton games) it writes a timestamped
backup. `--remove-missing` only ever prunes shortcuts **deckport itself tagged** —
it leaves other tools' shortcuts alone.

## Why non-Steam shortcuts instead of "real" Steam entries?

These games aren't on Steam, so a non-Steam shortcut is the supported way to get
them into the library and Game Mode. It's the same mechanism the "Add a Non-Steam
Game" button uses — deckport just does it in bulk, with correct artwork and (for
Windows games) the Proton compatibility tool set for you.

## Does deckport download games for me?

No, and it never will. deckport moves a folder **you already have** and configures
how it runs. Recipes describe configuration and link to community guides /
storefronts — they never link to where game files can be obtained, and a content
denylist in CI rejects any recipe that tries.

## What's a "recipe"?

One TOML file per game describing how to make it run: the binary, required data
files, launch options, and (for Windows games) the Proton version. The recipe
book is the community-curated part of the project — see
`deckport-recipes/RECIPE_FORMAT.md`. You can write one by hand, scaffold one from
a real folder with `deckport-recipe`, or use the website's **Suggest a recipe**
form.

## What do the recipe statuses mean?

- **unverified** — guessed/auto-generated, never run.
- **needs-test** — structure checked (engine, binary, data files), not launched.
- **working** — confirmed running on a real Deck, with the SteamOS build recorded.
- **borked** — confirmed it does *not* run, with notes on why.

A recipe only becomes `working` after a real person verifies it on real hardware
(see `docs/VERIFICATION.md`). The website's community 👍 "verified" badge is a
*separate* signal from this maintainer status.

## Will a SteamOS update wipe my imported games?

No. Your games, `shortcuts.vdf`, and grid artwork live in `/home`, which survives
updates. The only thing an update can revert is the SSH server enable — re-run
`scripts/deck-enable-ssh.sh` if `deckport-push` can't connect afterward.

## Does it work with Windows games?

Yes, via Proton. A `type = "proton"` recipe with a `[proton] version` makes the
importer register the shortcut **and** set the Proton compatibility tool
automatically. The usual blocker for old/delisted titles is DRM, not rendering —
deckport configures the prefix but never bundles or circumvents DRM.

## Can I undo an import?

Yes. Either delete the game folder from `~/Games/` and run `--remove-missing`, or
restore the `shortcuts.vdf.bak.<timestamp>` backup (with Steam closed).

## Is it on Steam Deck only?

It's built and tested against SteamOS, but the importer works on any Linux machine
running Steam (the paths and `shortcuts.vdf` format are the same).
