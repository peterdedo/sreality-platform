/**
 * Vercel Edge Middleware — API key injection + /health routing.
 *
 * Railway currently has no active public deployment, so this middleware
 * MUST NOT rewrite /health or /api/* to the Railway origin. Doing that
 * bypasses Vercel functions (frontend/api/*) which try Railway and then
 * serve a demo fallback so the SPA stays usable.
 *
 * 1. Rewrites /health → /api/health (Vercel Edge function).
 * 2. Injects X-API-Key for write/export paths so the SPA never embeds the
 *    secret (no VITE_API_KEY in the client bundle). Functions then proxy
 *    the request to Railway when it is up.
 *
 * Set the same API_KEY on Vercel (server/edge env) and Railway.
 * Local Vite uses vite.config.ts proxy injection instead.
 *
 * IMPORTANT: headers must be set under `request.headers` so they are forwarded
 * to the function. Top-level `headers` are response headers.
 */
import { next, rewrite } from "@vercel/edge";

const PROTECTED_PATHS = [
  /^\/api\/scraping\/(trigger|backfill-missing-details|backfill-price-units|reconcile-orphaned-runs|prune-raw-payloads)\/?$/,
  /^\/api\/analytics\/advanced\/recompute\/?$/,
  /^\/api\/export\//,
];

function isBackendPath(pathname) {
  return pathname === "/health" || pathname.startsWith("/health/") || pathname === "/api" || pathname.startsWith("/api/");
}

function withApiKey(request) {
  const { pathname } = new URL(request.url);
  const needsKey = PROTECTED_PATHS.some((re) => re.test(pathname));
  if (!needsKey) return null;

  const apiKey = process.env.API_KEY;
  if (!apiKey) {
    return new Response(
      JSON.stringify({
        detail: "API_KEY není nastavený ve Vercel Edge env. Nastavte API_KEY (stejný jako na Railway).",
      }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("X-API-Key", apiKey);
  return requestHeaders;
}

export default function middleware(request) {
  const { pathname, search } = new URL(request.url);

  if (pathname === "/health" || pathname === "/health/") {
    const headers = withApiKey(request);
    if (headers instanceof Response) return headers;
    return rewrite(new URL(`/api/health${search}`, request.url), {
      request: { headers: headers ?? request.headers },
    });
  }

  if (!isBackendPath(pathname)) {
    return next();
  }

  const headers = withApiKey(request);
  if (headers instanceof Response) return headers;
  if (!headers) return next();
  return next({ request: { headers } });
}

export const config = {
  matcher: ["/health", "/health/", "/api", "/api/:path*"],
};
