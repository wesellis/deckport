// @ts-check
import { defineConfig } from "astro/config";

// Static recipe-book site. Pure SSG output (dist/) that any static host —
// or nginx on a DigitalOcean droplet — can serve directly. No backend, no
// Node runtime required in production (decision D3).
//
// When the site gets its real domain, set `site` so canonical URLs and any
// sitemap are correct, e.g. site: "https://deckport.example".
export default defineConfig({
  output: "static",
  trailingSlash: "ignore",
  build: {
    format: "directory",
  },
});
