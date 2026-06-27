// Build-time lookup of cached Steam screenshots per recipe (thumb + full URLs).
// Populate with `node scripts/fetch-shots.mjs`. We link Steam's CDN, host nothing.
import cache from "./shot-cache.json";

export interface Shot {
  t: string; // thumbnail
  f: string; // full-size
}

const map = cache as Record<string, Shot[]>;

export function shots(slug: string): Shot[] {
  return map[slug] ?? [];
}
