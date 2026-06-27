// Build-time lookup of the cached SteamGridDB HERO (wide banner) per recipe.
// Populate with `node scripts/fetch-heroes.mjs` (needs STEAMGRIDDB_API_KEY). The
// recipe detail page uses this as its poster background, falling back to the
// landscape grid when a game has no hero.
import cache from "./hero-cache.json";

const map = cache as Record<string, string | null>;

export function heroUrl(slug: string): string | null {
  return map[slug] ?? null;
}
