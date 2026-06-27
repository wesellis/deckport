// Build-time recipe loader.
//
// Reads every TOML file in the sibling `deckport-recipes/recipes/` folder and
// turns it into a typed object the site renders. This runs in Node during the
// static build only — nothing here ships to the browser. Git stays the database
// (decision D2); this module is just the static-build view of it (D3).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse as parseToml } from "smol-toml";

export type RecipeStatus = "working" | "needs-test" | "unverified" | "borked";

export const STATUS_ORDER: RecipeStatus[] = [
  "working",
  "needs-test",
  "unverified",
  "borked",
];

export const STATUS_LABEL: Record<RecipeStatus, string> = {
  working: "Working",
  "needs-test": "Needs test",
  unverified: "Unverified",
  borked: "Borked",
};

// ProtonDB medal tiers. These exist only for games on Steam (ProtonDB keys off
// the Steam appid). A native-Linux or non-Steam game has no tier — that's fine.
// A recipe's tier is a *cached community hint*, never our own verification.
export type ProtonTier =
  | "platinum"
  | "gold"
  | "silver"
  | "bronze"
  | "borked"
  | "pending";

export const PROTON_TIERS: Record<
  ProtonTier,
  { label: string; color: string; note: string }
> = {
  platinum: { label: "Platinum", color: "#b8c6db", note: "runs flawlessly" },
  gold: { label: "Gold", color: "#cfb53b", note: "runs perfectly after tweaks" },
  silver: { label: "Silver", color: "#aab2bd", note: "runs with minor issues" },
  bronze: { label: "Bronze", color: "#cd7f32", note: "runs, but with problems" },
  borked: { label: "Borked", color: "#c0392b", note: "does not run under Proton" },
  pending: { label: "Pending", color: "#8595a8", note: "not enough reports yet" },
};

export const PROTON_TIER_ORDER: ProtonTier[] = [
  "platinum",
  "gold",
  "silver",
  "bronze",
  "borked",
  "pending",
];

export function normalizeTier(v: string): ProtonTier | null {
  const s = v.trim().toLowerCase();
  return s in PROTON_TIERS ? (s as ProtonTier) : null;
}

export interface Guide {
  title: string;
  url: string;
}

export interface Recipe {
  // [game]
  title: string;
  slug: string;
  aliases: string[];
  type: "native" | "proton";
  engine: string;
  steamAppid: string;
  sgdbId: string;
  // [launch]
  binary: string;
  launchOptions: string;
  requiresFiles: string[];
  // [proton]
  protonVersion: string;
  winetricks: string[];
  protonNotes: string;
  // [art]
  art: { cover: string; hero: string; logo: string; icon: string };
  // [links]
  protondbUrl: string; // explicit override; else derived from steamAppid
  sgdbUrl: string; // explicit override; else derived from sgdbId / title search
  guides: Guide[]; // community write-ups: Reddit threads, blog posts, videos
  // [meta]
  status: RecipeStatus;
  verifiedOn: string;
  contributor: string;
  protondbTier: string;
  caveats: string;
  // [about] — optional encyclopedic facts so the page stands on its own
  about: {
    developer: string;
    publisher: string;
    released: string;
    genre: string;
    modes: string;
    summary: string;
  };
  // derived
  sourceFile: string; // filename, for the "edit on GitHub" link
}

// The GitHub repo path to the recipes folder, used to build "edit this recipe"
// links. Update the org/repo here once the public repo name is final.
export const RECIPES_REPO =
  "https://github.com/wesellis/deckport/blob/main/deckport-recipes/recipes";

const RECIPES_DIR = fileURLToPath(
  new URL("../../../deckport-recipes/recipes", import.meta.url),
);

function asString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function asStringArray(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

function asGuides(v: unknown): Guide[] {
  if (!Array.isArray(v)) return [];
  return v
    .map((g): Guide | null => {
      if (g && typeof g === "object") {
        const title = asString((g as any).title);
        const url = asString((g as any).url);
        if (url) return { title: title || url, url };
      }
      return null;
    })
    .filter((g): g is Guide => g !== null);
}

function normalizeStatus(v: unknown): RecipeStatus {
  const s = asString(v).toLowerCase();
  if (s === "working" || s === "needs-test" || s === "borked") return s;
  return "unverified";
}

function loadOne(file: string): Recipe {
  const raw = fs.readFileSync(path.join(RECIPES_DIR, file), "utf8");
  const t = parseToml(raw) as Record<string, any>;
  const game = t.game ?? {};
  const launch = t.launch ?? {};
  const proton = t.proton ?? {};
  const art = t.art ?? {};
  const links = t.links ?? {};
  const meta = t.meta ?? {};
  const about = t.about ?? {};

  const slugFromName = file.replace(/\.toml$/i, "");
  const slug = asString(game.slug, slugFromName);
  if (slug !== slugFromName) {
    // The format doc requires slug === filename. Warn loudly at build time
    // rather than silently shipping a mismatched URL.
    console.warn(
      `[recipes] slug "${slug}" does not match filename "${file}" — using filename.`,
    );
  }

  return {
    title: asString(game.title, slugFromName),
    slug: slugFromName,
    aliases: asStringArray(game.aliases),
    type: asString(game.type, "native") === "proton" ? "proton" : "native",
    engine: asString(game.engine, "other"),
    steamAppid: asString(game.steam_appid),
    sgdbId: asString(game.sgdb_id),
    binary: asString(launch.binary),
    launchOptions: asString(launch.launch_options),
    requiresFiles: asStringArray(launch.requires_files),
    protonVersion: asString(proton.version),
    winetricks: asStringArray(proton.winetricks),
    protonNotes: asString(proton.notes),
    art: {
      cover: asString(art.cover, "auto"),
      hero: asString(art.hero, "auto"),
      logo: asString(art.logo, "auto"),
      icon: asString(art.icon, "auto"),
    },
    protondbUrl: asString(links.protondb),
    sgdbUrl: asString(links.steamgriddb),
    guides: asGuides(links.guides),
    status: normalizeStatus(meta.status),
    verifiedOn: asString(meta.verified_on),
    contributor: asString(meta.contributor),
    protondbTier: asString(meta.protondb_tier),
    caveats: asString(meta.caveats),
    about: {
      developer: asString(about.developer),
      publisher: asString(about.publisher),
      released: asString(about.released),
      genre: asString(about.genre),
      modes: asString(about.modes),
      summary: asString(about.summary),
    },
    sourceFile: file,
  };
}

let cache: Recipe[] | null = null;

export function getAllRecipes(): Recipe[] {
  if (cache) return cache;
  let files: string[] = [];
  try {
    files = fs
      .readdirSync(RECIPES_DIR)
      .filter((f) => f.endsWith(".toml") && !f.startsWith("_"));
  } catch (e) {
    console.warn(`[recipes] could not read ${RECIPES_DIR}:`, e);
    files = [];
  }

  const recipes = files.map(loadOne);

  // Sort: working first, then needs-test, unverified, borked; alpha within a
  // status. The list view leans on this so confidence reads top-to-bottom.
  recipes.sort((a, b) => {
    const sa = STATUS_ORDER.indexOf(a.status);
    const sb = STATUS_ORDER.indexOf(b.status);
    if (sa !== sb) return sa - sb;
    return a.title.localeCompare(b.title);
  });

  cache = recipes;
  return recipes;
}

export function getRecipe(slug: string): Recipe | undefined {
  return getAllRecipes().find((r) => r.slug === slug);
}

export function statusCounts(): Record<RecipeStatus, number> {
  const counts: Record<RecipeStatus, number> = {
    working: 0,
    "needs-test": 0,
    unverified: 0,
    borked: 0,
  };
  for (const r of getAllRecipes()) counts[r.status]++;
  return counts;
}

// Only ever hand an http(s) URL to an href. Recipe links are community data;
// without this an explicit `links.steamgriddb = "javascript:..."` would render
// a clickable XSS link. Anything not http(s) is dropped (returns null).
export function safeUrl(u: string | null | undefined): string | null {
  if (!u) return null;
  return /^https?:\/\//i.test(u.trim()) ? u.trim() : null;
}

// Best ProtonDB report URL for a recipe, or null if it isn't a Steam game.
// ProtonDB is keyed by Steam appid, so there's no useful name-search fallback.
export function protondbLink(r: Recipe): string | null {
  if (r.protondbUrl) return safeUrl(r.protondbUrl);
  if (r.steamAppid) return `https://www.protondb.com/app/${encodeURIComponent(r.steamAppid)}`;
  return null;
}

// Best SteamGridDB URL — always returns something, falling back to a name
// search so a user can always go find and pick their own artwork.
export function sgdbLink(r: Recipe): string {
  const explicit = safeUrl(r.sgdbUrl);
  if (explicit) return explicit;
  if (r.sgdbId) return `https://www.steamgriddb.com/game/${encodeURIComponent(r.sgdbId)}`;
  return `https://www.steamgriddb.com/search/grids?term=${encodeURIComponent(r.title)}`;
}

// Render a recipe prose field (notes / caveats / summary) as safe HTML with a
// tiny, fixed markup subset, so the text can have structure instead of being a
// flat paragraph. Used with Astro's `set:html`. Supported markup:
//   **bold**      -> <strong>   (key terms, "Label:" leads)
//   `code`        -> <code>     (exe names, launch options, Proton versions)
//   blank line    -> paragraph break;  single newline -> line break
// Everything is HTML-escaped FIRST, then only these controlled tags are added,
// so a recipe string can never inject markup (defence-in-depth — data is repo-
// controlled, but we never trust it into innerHTML raw).
export function fmtProse(s: string): string {
  if (!s) return "";
  const esc = (x: string) =>
    x.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inline = (x: string) =>
    esc(x)
      .replace(/`([^`]+)`/g, (_m, c) => `<code>${c}</code>`)
      .replace(/\*\*([^*]+)\*\*/g, (_m, c) => `<strong>${c}</strong>`);
  // Split on blank lines into paragraphs; single newlines become <br>.
  return s
    .split(/\n[ \t]*\n/)
    .map((para) => `<p>${inline(para.trim()).replace(/\r?\n/g, "<br>")}</p>`)
    .join("");
}
