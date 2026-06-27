# Troubleshooting

Common failures and how to fix them. Most issues are one of: Steam was open while
importing, the binary lost its execute bit in transit, or art was named for the
wrong app ID.

## The game doesn't appear in Game Mode

- **Steam was running during the import.** Steam rewrites `shortcuts.vdf` when it
  exits, wiping changes made while it was open. Fully quit Steam, re-run the
  importer, then reopen Steam. The importer refuses to write while Steam is
  running for exactly this reason.
- **No Linux binary was found.** Run with `--dry-run`: if the folder is listed as
  skipped ("no Linux executable found"), the game may be Windows-only (a `.exe` —
  use a `type = "proton"` recipe) or the binary is nested deeper than the scan
  goes. Point a recipe's `binary` at the exact file.
- **Wrong Steam user.** If you have multiple Steam accounts, pass
  `--user <steamID3>` so it writes to the right `userdata/<id>/`.

## The game appears but won't launch

- **Missing execute bit.** Copying over SFTP/USB/zip strips the `+x` flag. The
  importer sets it automatically; if you bypassed it, run
  `chmod +x ~/Games/<Game>/<binary>`.
- **Missing data files.** Godot games need their `.pck`; LÖVE needs the `.love`
  beside (or fused into) the runtime. List them in the recipe's `requires_files`
  so the importer warns instead of registering a broken shortcut.
- **LÖVE with no runtime.** A `.love` needs a `love` runtime on the Deck (Flatpak
  or AppImage) unless it's a fused Linux AppImage.

## No artwork (or the wrong artwork)

- **Fetched into the wrong place.** Art must end up in
  `<Game>/.deckport-art/` before the import; the importer renames it to
  `{appid}…` in Steam's `grid/` folder. Re-run `deckport-art` and check that
  folder exists.
- **Name didn't match on SteamGridDB.** `deckport-art --dry-run` shows the match
  it picked. If it's wrong, pass `--name "Exact Title"` (or set the recipe's
  `sgdb_id`).
- **Stale art after a rename.** If you renamed the game (changing its app ID), the
  old grid files are orphaned. `--remove-missing` cleans orphans whose folder is
  gone; otherwise delete the old `{appid}*` files from `grid/`.

## `deckport-art` errors

- **`no SteamGridDB API key`** — get a free key at steamgriddb.com and pass
  `--api-key` or set `STEAMGRIDDB_API_KEY`.
- **A `401` on an image download** — fixed in current builds (the public CDN
  rejects the API auth header). Update to the latest.

## `deckport-push` can't reach the Deck

- **SSH not enabled.** Run `scripts/deck-enable-ssh.sh` on the Deck (Desktop Mode).
  SteamOS updates can revert the sshd enable — just re-run it; your games and
  shortcuts in `/home` survive.
- **`neither rsync nor scp found`** — install OpenSSH client on your PC (it ships
  with Windows 10+, macOS, and most Linux). `rsync` is optional; `scp` is the
  fallback.
- **Created a literal `~` folder** — fixed in current builds; remote paths are no
  longer over-quoted. Update.

## Proton game won't run (M6)

- The importer sets the Proton version from the recipe automatically; verify it in
  **Properties → Compatibility**. If it's blank, the recipe had no
  `[proton] version`.
- **DRM is the usual blocker** for delisted/disc-era titles (e.g. SecuROM), not
  the renderer. Check the recipe's community guides. deckport configures the
  prefix; it never bundles or defeats DRM.

## After a SteamOS update

- Your games, `shortcuts.vdf`, and grid art live in `/home` and **survive
  updates**. Only the sshd enable can revert — re-run `scripts/deck-enable-ssh.sh`.

## Recovering `shortcuts.vdf`

Every write backs up the previous file to
`shortcuts.vdf.bak.<timestamp>` next to it. Close Steam, restore the backup over
`shortcuts.vdf`, reopen Steam.
