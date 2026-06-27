// Site-wide config. Tip jar URL — set to your Ko-fi / Buy Me a Coffee / GitHub
// Sponsors page, or "" to hide the Support links everywhere. Override at build
// time with PUBLIC_SUPPORT_URL. Confirm/replace the handle before going live.
export const SUPPORT_URL =
  import.meta.env.PUBLIC_SUPPORT_URL || "https://ko-fi.com/mookyjooky";

// Prefix an internal absolute path with the site base so links work both at the
// domain root ("/") and under a GitHub Pages subpath ("/deckport/").
// withBase("/recipes") -> "/recipes" or "/deckport/recipes".
export const withBase = (p: string): string =>
  import.meta.env.BASE_URL.replace(/\/$/, "") + "/" + p.replace(/^\//, "");

