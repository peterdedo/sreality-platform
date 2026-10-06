/** Shared Railway origin probe + JSON proxy for Vercel serverless/edge. */

export const RAILWAY_ORIGIN = (
  process.env.BACKEND_URL || "https://sreality-platform-production.up.railway.app"
).replace(/\/$/, "");

export function isRailwayMiss(status, body) {
  if (body && typeof body === "object") {
    if (body.message === "Application not found") return true;
    if (body.status === "error" && body.code === 404) return true;
  }
  if (status !== 404) return false;
  if (!body || typeof body !== "object") return true;
  return !("items" in body) && !("active_listing_count" in body);
}

function railwayPath(pathname, search) {
  const path = pathname.replace(/\/$/, "") || "/";
  if (path === "/api/health" || path === "/health") return `/health${search}`;
  return `${pathname}${search}`;
}

export async function proxyRailway(request, pathnameWithSearch) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8_000);
  try {
    const headers = new Headers();
    headers.set("Accept", "application/json");
    const apiKey = request.headers.get("x-api-key");
    if (apiKey) headers.set("X-API-Key", apiKey);
    const init = {
      method: request.method,
      headers,
      signal: controller.signal,
    };
    if (request.method !== "GET" && request.method !== "HEAD") {
      const contentType = request.headers.get("content-type");
      if (contentType) headers.set("content-type", contentType);
      init.body = await request.arrayBuffer();
    }
    const res = await fetch(`${RAILWAY_ORIGIN}${pathnameWithSearch}`, init);
    const contentType = res.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) return null;
    const body = await res.json();
    if (isRailwayMiss(res.status, body)) return null;
    return { status: res.status, body };
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export function json(status, body, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...extraHeaders,
    },
  });
}

export function effectiveRequestUrl(request) {
  const url = new URL(request.url);
  const fromHeader = request.headers.get("x-sreality-original-path");
  const fromQuery = url.searchParams.get("__orig_path");
  url.searchParams.delete("__orig_path");
  if (fromHeader) {
    const original = new URL(fromHeader, url.origin);
    original.searchParams.delete("__orig_path");
    return original;
  }
  if (fromQuery) {
    const original = new URL(fromQuery, url.origin);
    for (const [key, value] of url.searchParams.entries()) {
      if (!original.searchParams.has(key)) original.searchParams.set(key, value);
    }
    original.searchParams.delete("__orig_path");
    return original;
  }
  return url;
}

export async function dispatchApi(request, handleFallback) {
  const url = effectiveRequestUrl(request);
  const proxied = await proxyRailway(request, railwayPath(url.pathname, url.search));
  if (proxied) {
    return json(proxied.status, proxied.body, { "x-sreality-data-source": "railway" });
  }
  const path = url.pathname.replace(/\/$/, "") || "/";
  const fallback = handleFallback(request.method, path, url.searchParams);
  return json(fallback.status, fallback.body, { "x-sreality-data-source": "vercel-fallback" });
}
