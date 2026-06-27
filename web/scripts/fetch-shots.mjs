// Cache up to 5 screenshots per recipe from Steam's store API into
// src/lib/shot-cache.json. Steam still serves screenshots for most delisted
// games (the store page lingers even when it's not buyable). We link Steam's CDN
// — we host nothing. Native / non-Steam recipes (no appid) just get an empty list.
//
//   node scripts/fetch-shots.mjs                       # fill gaps, all recipes
//   node scripts/fetch-shots.mjs --force               # refetch all
//   node scripts/fetch-shots.mjs street-fighter-x-tekken   # just one (testing)
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse as parseToml } from "smol-toml";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RECIPES = path.join(HERE, "../../deckport-recipes/recipes");
const CACHE = path.join(HERE, "../src/lib/shot-cache.json");
const MAX = 5;

const force = process.argv.includes("--force");
const onlySlug = process.argv.slice(2).find((a) => !a.startsWith("--"));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function shotsFor(appid) {
  const url = `https://store.steampowered.com/api/appdetails?appids=${appid}&filters=screenshots&cc=us&l=en`;
  for (let attempt = 0; attempt < 3; attempt++) {
    const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
    if (r.status === 429) {
      await sleep(5000 * (attempt + 1));
      continue;
    }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    const app = d?.[appid];
    if (!app?.success) return [];
    const shots = app.data?.screenshots ?? [];
    return shots.slice(0, MAX).map((s) => ({ t: s.path_thumbnail, f: s.path_full }));
  }
  throw new Error("rate-limited");
}

let files = readdirSync(RECIPES).filter((f) => f.endsWith(".toml") && !f.startsWith("_"));
if (onlySlug) files = files.filter((f) => f === `${onlySlug}.toml`);
const cache = existsSync(CACHE) ? JSON.parse(readFileSync(CACHE, "utf8")) : {};

for (const f of files) {
  const slug = f.replace(/\.toml$/, "");
  if (!force && slug in cache) continue;
  const t = parseToml(readFileSync(path.join(RECIPES, f), "utf8"));
  const appid = String(t.game?.steam_appid ?? "").trim();
  if (!/^\d+$/.test(appid)) {
    cache[slug] = []; // no Steam appid → no screenshots
    continue;
  }
  try {
    const shots = await shotsFor(appid);
    cache[slug] = shots;
    console.log(`${shots.length ? "✓" : "·"} ${slug} (${shots.length})`);
    await sleep(350); // be polite to Steam's API
  } catch (e) {
    console.warn(`! ${slug}: ${e.message}`);
    if (!(slug in cache)) cache[slug] = [];
  }
}

// Keep only live recipes (unless single-slug run), write sorted.
const allLive = new Set(
  readdirSync(RECIPES)
    .filter((f) => f.endsWith(".toml") && !f.startsWith("_"))
    .map((f) => f.replace(/\.toml$/, "")),
);
const sorted = Object.fromEntries(
  Object.keys(cache)
    .filter((k) => allLive.has(k))
    .sort()
    .map((k) => [k, cache[k]]),
);
writeFileSync(CACHE, JSON.stringify(sorted) + "\n");
const withShots = Object.values(sorted).filter((v) => v.length).length;
console.log(`\nwrote ${path.relative(process.cwd(), CACHE)} — ${withShots} recipes with screenshots`);
