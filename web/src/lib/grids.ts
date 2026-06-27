// Build-time lookup of the cached SteamGridDB landscape grid per recipe.
// Populate the cache with `npm run grids` (needs STEAMGRIDDB_API_KEY). The build
// only reads this JSON, so it stays offline and fast; a missing entry just means
// the card renders without a banner.
import cache from "./grid-cache.json";

const map = cache as Record<string, string | null>;

export function gridUrl(slug: string): string | null {
  return map[slug] ?? null;
}
