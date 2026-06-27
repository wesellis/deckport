// @ts-check
import { defineConfig } from "astro/config";

// Static recipe-book site. Pure SSG output (dist/) that any static host can
// serve. Served at the domain ROOT on a droplet/custom-domain, or at /<repo>/
// on GitHub Pages — the Pages workflow sets PUBLIC_BASE_PATH=/deckport, and all
// internal links go through withBase() (src/lib/site.ts) so they resolve under
// either. Override the canonical host with PUBLIC_SITE_URL.
const base = process.env.PUBLIC_BASE_PATH || "/";

export default defineConfig({
  site: process.env.PUBLIC_SITE_URL || "https://wesellis.github.io",
  base,
  output: "static",
  trailingSlash: "ignore",
  build: {
    format: "directory",
  },
});
