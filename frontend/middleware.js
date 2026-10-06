/**
 * Vercel Edge Middleware — API key injection + API gateway routing.
 *
 * Nested /api/* paths do not hit api/[...path].js on this Vite + outputDirectory
 * project (Vercel returns NOT_FOUND). All backend paths are rewritten to the
 * one-segment function /api/gateway, which tries Railway then serves demo data.
 *
 * 1. Rewrites /health and /api/* → /api/gateway (except /api/gateway itself).
 * 2. Injects X-API-Key for write/export paths so the SPA never embeds the secret.
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

const GATEWAY = "/api/gateway";

function isBackendPath(pathname) {
  return pathname === "/health" || pathname.startsWith("/health/") || pathname === "/api" || pathname.startsWith("/api/");
}

function withApiKey(request, pathname) {
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

function gatewayHeaders(request, pathname, search) {
  const keyHeaders = withApiKey(request, pathname);
  if (keyHeaders instanceof Response) return keyHeaders;
  const headers = new Headers(keyHeaders ?? request.headers);
  headers.set("x-sreality-original-path", `${pathname}${search}`);
  return headers;
}

export default function middleware(request) {
  const { pathname, search } = new URL(request.url);

  if (pathname === GATEWAY || pathname === "/api/health") {
    const originalPath = request.headers.get("x-sreality-original-path") ?? pathname;
    const headers = withApiKey(request, originalPath.split("?")[0]);
    if (headers instanceof Response) return headers;
    if (!headers) return next();
    return next({ request: { headers } });
  }

  if (!isBackendPath(pathname)) {
    return next();
  }

  const headers = gatewayHeaders(request, pathname, search);
  if (headers instanceof Response) return headers;
  const dest = new URL(`${GATEWAY}${search}`, request.url);
  dest.searchParams.set("__orig_path", pathname);
  return rewrite(dest, { request: { headers } });
}

export const config = {
  matcher: ["/health", "/health/", "/api", "/api/:path*"],
};
