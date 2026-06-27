// Resolve a Steam horizontal (landscape) grid image for each recipe from
// SteamGridDB, and cache the URLs to src/lib/grid-cache.json. The static build
// reads only the cache — this network step runs occasionally, not every build.
//
//   STEAMGRIDDB_API_KEY=... node scripts/fetch-grids.mjs           # fill gaps
//   STEAMGRIDDB_API_KEY=... node scripts/fetch-grids.mjs --force   # refetch all
//
// We link the SteamGridDB CDN (we host nothing — decision D8/D2). A recipe with
// no match just gets `null` and renders without a banner.
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse as parseToml } from "smol-toml";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RECIPES = path.join(HERE, "../../deckport-recipes/recipes");
const CACHE = path.join(HERE, "../src/lib/grid-cache.json");
const BASE = "https://www.steamgriddb.com/api/v2";

const KEY = process.env.STEAMGRIDDB_API_KEY;
const force = process.argv.includes("--force");

if (!KEY) {
  console.error("error: set STEAMGRIDDB_API_KEY (free key at steamgriddb.com).");
  process.exit(1);
}

async function sgdb(p) {
  const r = await fetch(BASE + p, { headers: { Authorization: `Bearer ${KEY}` } });
  if (!r.ok) throw new Error(`${r.status} on ${p}`);
  return r.json();
}

async function resolveGameId(rec) {
  if (rec.sgdb_id) return rec.sgdb_id;
  // A Steam appid maps straight to a SteamGridDB game — far more accurate than
  // name-matching, so prefer it when the recipe has one.
  if (rec.steam_appid) {
    try {
      const r = await sgdb(`/games/steam/${encodeURIComponent(rec.steam_appid)}`);
      if (r.data?.id) return r.data.id;
    } catch {
      /* fall through to name search */
    }
  }
  // Try the title, then each alias — odd titles often miss but an alias hits.
  for (const term of [rec.title, ...(rec.aliases || [])]) {
    if (!term) continue;
    const r = await sgdb(`/search/autocomplete/${encodeURIComponent(term)}`);
    if (r.data?.[0]?.id) return r.data[0].id;
  }
  return null;
}

async function resolveGrid(id) {
  const clean = (list) => (list || []).filter((g) => !g.nsfw && !g.humor);
  const pickUrl = (g) => g && (g.thumb || g.url);
  // Prefer the OLDEST upload (lowest id) — usually the original capsule, before
  // the platform-labelled / fan-made variants pile on top.
  const oldest = (arr) => (arr.length ? [...arr].sort((a, b) => a.id - b.id)[0] : null);
  // 1) the standard horizontal capsule dimensions (pull a wide set so the oldest is in it).
  let list = clean(
    (await sgdb(`/grids/game/${id}?dimensions=460x215,920x430&types=static&nsfw=false&limit=50`)).data,
  );
  // 2) any static grid that's landscape (width > height), any size.
  if (!list.length) {
    const all = clean((await sgdb(`/grids/game/${id}?types=static&nsfw=false&limit=50`)).data);
    list = all.filter((g) => g.width > g.height);
  }
  if (list.length) return pickUrl(oldest(list));
  // 3) portrait grid — box art with the game logo baked in. Crops better than a hero
  //    screenshot and still identifies the game clearly. Prefer over hero banners.
  const anyGrid = clean((await sgdb(`/grids/game/${id}?types=static&nsfw=false&limit=50`)).data);
  if (anyGrid.length) return pickUrl(oldest(anyGrid));
  // 4) last resort: a hero banner — wide but often no logo text.
  const heroes = clean((await sgdb(`/heroes/game/${id}?types=static&nsfw=false&limit=10`)).data);
  return pickUrl(oldest(heroes)) || null;
}

const files = readdirSync(RECIPES).filter((f) => f.endsWith(".toml") && !f.startsWith("_"));
const cache = existsSync(CACHE) ? JSON.parse(readFileSync(CACHE, "utf8")) : {};

for (const f of files) {
  const slug = f.replace(/\.toml$/, "");
  if (!force && cache[slug]) continue; // keep hits; retry misses (null) and new ones
  const t = parseToml(readFileSync(path.join(RECIPES, f), "utf8"));
  const rec = {
    title: t.game?.title ?? slug,
    sgdb_id: t.game?.sgdb_id ?? "",
    steam_appid: t.game?.steam_appid ?? "",
    aliases: t.game?.aliases ?? [],
  };
  try {
    const id = await resolveGameId(rec);
    const url = id ? await resolveGrid(id) : null;
    cache[slug] = url;
    console.log(`${url ? "✓" : "·"} ${slug}${url ? "" : "  (no grid found)"}`);
  } catch (e) {
    console.warn(`! ${slug}: ${e.message}`);
    if (!(slug in cache)) cache[slug] = null;
  }
}

// Drop cache entries whose recipe was deleted, and write sorted for clean diffs.
const live = new Set(files.map((f) => f.replace(/\.toml$/, "")));
const sorted = Object.fromEntries(
  Object.keys(cache)
    .filter((k) => live.has(k))
    .sort()
    .map((k) => [k, cache[k]]),
);
writeFileSync(CACHE, JSON.stringify(sorted, null, 2) + "\n");
const hits = Object.values(sorted).filter(Boolean).length;
console.log(`\nwrote ${path.relative(process.cwd(), CACHE)} — ${hits}/${files.length} with a grid`);
