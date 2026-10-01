/**
 * Vercel Edge Middleware — injects X-API-Key for write/export paths so the
 * SPA never embeds the secret (no VITE_API_KEY in the client bundle).
 *
 * Set the same API_KEY on Vercel (server/edge env) and Railway.
 * Local Vite uses vite.config.ts proxy injection instead.
 */
import { next } from "@vercel/edge";

const PROTECTED_PATHS = [
  /^\/api\/scraping\/(trigger|backfill-missing-details|reconcile-orphaned-runs|prune-raw-payloads)\/?$/,
  /^\/api\/analytics\/advanced\/recompute\/?$/,
  /^\/api\/export\//,
];

export default function middleware(request) {
  const { pathname } = new URL(request.url);
  const needsKey = PROTECTED_PATHS.some((re) => re.test(pathname));
  if (!needsKey) {
    return next();
  }

  const apiKey = process.env.API_KEY;
  if (!apiKey) {
    return new Response(
      JSON.stringify({
        detail: "API_KEY není nastavený ve Vercel Edge env. Nastavte API_KEY (stejný jako na Railway).",
      }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }

  return next({
    headers: {
      "X-API-Key": apiKey,
    },
  });
}

export const config = {
  matcher: [
    "/api/scraping/trigger",
    "/api/scraping/backfill-missing-details",
    "/api/scraping/reconcile-orphaned-runs",
    "/api/scraping/prune-raw-payloads",
    "/api/analytics/advanced/recompute",
    "/api/export/:path*",
  ],
};
