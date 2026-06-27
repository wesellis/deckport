// Per-recipe install helper script, generated at build time.
//
// Route: /scripts/<slug>.deckport.sh  (a real static file in dist/)
// The recipe page links to it with a `download` attribute. The user drops it on
// their Steam Deck and runs it; it does the mechanical part of an import for
// that specific game and prints the steps the importer can't yet do for itself.
//
// It only ever calls the existing importer (deckport.py) — it never fetches or
// distributes game files (decision D8).

import type { APIRoute } from "astro";
import { getAllRecipes, getRecipe, type Recipe } from "../../lib/recipes";

export function getStaticPaths() {
  // Skip borked recipes — they don't run, so an install script would mislead.
  return getAllRecipes()
    .filter((r) => r.status !== "borked")
    .map((r) => ({ params: { slug: r.slug } }));
}

// Escape a value for safe embedding inside a double-quoted bash string.
function shq(v: string): string {
  return v.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/`/g, "\\`").replace(/\$/g, "\\$");
}

// Escape a value as a TOML basic (double-quoted) string.
function tq(v: string): string {
  return (
    '"' +
    v
      .replace(/\\/g, "\\\\")
      .replace(/"/g, '\\"')
      .replace(/\n/g, "\\n")
      .replace(/\r/g, "")
      .replace(/\t/g, "\\t") +
    '"'
  );
}
function tArr(a: string[]): string {
  return "[" + a.map(tq).join(", ") + "]";
}

// Minimal recipe TOML — only the fields the importer reads to apply a game
// (pinned binary, launch options, Proton version, required files). No notes/
// caveats: they aren't used by the import and would just complicate escaping.
function recipeToToml(r: Recipe): string {
  return [
    "[game]",
    `title = ${tq(r.title)}`,
    `slug = ${tq(r.slug)}`,
    `type = ${tq(r.type)}`,
    `engine = ${tq(r.engine)}`,
    `aliases = ${tArr(r.aliases)}`,
    `steam_appid = ${tq(r.steamAppid)}`,
    "",
    "[launch]",
    `binary = ${tq(r.binary)}`,
    `launch_options = ${tq(r.launchOptions)}`,
    `requires_files = ${tArr(r.requiresFiles)}`,
    "",
    "[proton]",
    `version = ${tq(r.protonVersion)}`,
    `winetricks = ${tArr(r.winetricks)}`,
    "",
    "[meta]",
    `status = ${tq(r.status)}`,
  ].join("\n");
}

function buildScript(r: Recipe): string {
  const requires = r.requiresFiles.map((f) => `"${shq(f)}"`).join(" ");

  // After the import, tell a Proton user what was applied + the one manual
  // dependency the importer can't satisfy: a GE-Proton build must already be
  // installed (ProtonUp-Qt). Native games need nothing extra.
  const afterBlock =
    r.type === "proton"
      ? [
          r.protonVersion
            ? `say "Proton applied automatically: ${shq(r.protonVersion)}"`
            : "",
          /ge[\s_-]?proton|proton[\s_-]?ge/i.test(r.protonVersion)
            ? `say "NOTE: this needs a GE-Proton build installed — add one via ProtonUp-Qt if the game won't launch."`
            : "",
          r.winetricks.length
            ? `say "winetricks this game expects: ${shq(r.winetricks.join(", "))}"`
            : "",
        ]
          .filter(Boolean)
          .join("\n")
      : `say "native Linux title — no Proton needed."`;

  const recipeToml = recipeToToml(r);

  const guideBlock = r.guides.length
    ? r.guides.map((g) => `#   - ${g.title}: ${g.url}`).join("\n")
    : "#   (none linked yet — see the recipe page)";

  return `#!/usr/bin/env bash
#
# deckport install helper — ${r.title}
# status: ${r.status} · engine: ${r.engine} · type: ${r.type}
#
# Generated from ${r.sourceFile} on the deckport recipe site.
# Recipes describe how to CONFIGURE a game — never where to obtain it.
#
# Community guides for this game:
${guideBlock}
#
# ON YOUR STEAM DECK (Desktop Mode), with STEAM CLOSED:
#   1. Copy the game's whole folder into ~/Games/
#   2. Put the importer in your home folder:  ~/deckport.py
#   3. Run:  bash ${r.slug}.deckport.sh
#
set -euo pipefail

GAMES_DIR="\${GAMES_DIR:-$HOME/Games}"
IMPORTER="\${IMPORTER:-$HOME/deckport.py}"
TAG="\${TAG:-Ported Games}"

GAME_TITLE="${shq(r.title)}"
BINARY="${shq(r.binary)}"
GAME_TYPE="${r.type}"
REQUIRES=(${requires})

say()  { printf '  %s\\n' "$*"; }
die()  { printf 'error: %s\\n' "$*" >&2; exit 1; }

printf '\\n=== deckport: %s ===\\n' "$GAME_TITLE"

[ -d "$GAMES_DIR" ] || die "drop directory $GAMES_DIR not found — create it and copy the game folder in"
[ -f "$IMPORTER" ]  || die "importer not found at $IMPORTER — copy deckport.py to your home folder"

# Refuse to clobber shortcuts.vdf while Steam is running (it rewrites on exit).
if pgrep -x steam >/dev/null 2>&1; then
  die "Steam is running — close it fully first, then re-run this script"
fi

# Locate the folder that holds the game binary.
GAME_DIR=""
if [ -n "$BINARY" ]; then
  GAME_DIR="$(find "$GAMES_DIR" -maxdepth 4 -name "$BINARY" -printf '%h\\n' 2>/dev/null | head -n1 || true)"
fi
[ -n "$GAME_DIR" ] || die "could not find '$BINARY' under $GAMES_DIR — copy the game folder there first"
say "found game folder: $GAME_DIR"

# Required data files must sit beside the binary.
for f in "\${REQUIRES[@]:-}"; do
  [ -z "$f" ] && continue
  if [ -e "$GAME_DIR/$f" ]; then say "ok: $f present"
  else die "missing required file: $f (must sit beside the binary)"; fi
done

# Write this game's recipe to a temp folder and hand it to the importer with
# --recipes, so it applies the PINNED binary, launch options and Proton version
# (not just auto-detect). Cleaned up on exit. Needs Python 3.11+ for TOML; if
# that's missing the importer says so and still registers the shortcut.
RECIPE_DIR="$(mktemp -d)"
trap 'rm -rf "$RECIPE_DIR"' EXIT
cat > "$RECIPE_DIR/${r.slug}.toml" <<'DECKPORT_RECIPE_TOML'
${recipeToml}
DECKPORT_RECIPE_TOML

say "registering with Steam (applying recipe)…"
python3 "$IMPORTER" --games-dir "$GAMES_DIR" --recipes "$RECIPE_DIR" --tag "$TAG"

${afterBlock}

printf '\\nDone. Reopen Steam / return to Game Mode — look under "%s".\\n\\n' "$TAG"
`;
}

export const GET: APIRoute = ({ params }) => {
  const slug = params.slug ?? "";
  const recipe = getRecipe(slug);
  if (!recipe) {
    return new Response("recipe not found\n", { status: 404 });
  }
  return new Response(buildScript(recipe), {
    headers: { "Content-Type": "text/x-shellscript; charset=utf-8" },
  });
};
