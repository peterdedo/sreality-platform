/**
 * Vercel Edge Middleware — API proxy + X-API-Key injection.
 *
 * 1. Rewrites /health and /api/* to the Railway backend at request time.
 *    BACKEND_URL (Vercel env) wins; otherwise the production Railway domain.
 *    vercel.json rewrites are the fallback if this matcher does not run.
 *
 * 2. Injects X-API-Key for write/export paths so the SPA never embeds the
 *    secret (no VITE_API_KEY in the client bundle).
 *
 * Set the same API_KEY on Vercel (server/edge env) and Railway.
 * Local Vite uses vite.config.ts proxy injection instead.
 *
 * IMPORTANT: headers must be set under `request.headers` so they are forwarded
 * to the Railway rewrite. Top-level `headers` are response headers and never
 * reach the backend (that caused production 401 on trigger/backfill).
 */
import { next, rewrite } from "@vercel/edge";

const DEFAULT_BACKEND = "https://sreality-platform-production.up.railway.app";

const PROTECTED_PATHS = [
  /^\/api\/scraping\/(trigger|backfill-missing-details|backfill-price-units|reconcile-orphaned-runs|prune-raw-payloads)\/?$/,
  /^\/api\/analytics\/advanced\/recompute\/?$/,
  /^\/api\/export\//,
];

function backendOrigin() {
  const fromEnv = (process.env.BACKEND_URL ?? "").trim().replace(/\/$/, "");
  return fromEnv || DEFAULT_BACKEND;
}

function isBackendPath(pathname) {
  return pathname === "/health" || pathname.startsWith("/health/") || pathname === "/api" || pathname.startsWith("/api/");
}

export default function middleware(request) {
  const { pathname, search } = new URL(request.url);
  if (!isBackendPath(pathname)) {
    return next();
  }

  const destination = new URL(pathname + search, `${backendOrigin()}/`);
  const needsKey = PROTECTED_PATHS.some((re) => re.test(pathname));
  if (!needsKey) {
    return rewrite(destination);
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

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("X-API-Key", apiKey);

  return rewrite(destination, {
    request: {
      headers: requestHeaders,
    },
  });
}

export const config = {
  matcher: ["/health", "/health/", "/api", "/api/:path*"],
};
