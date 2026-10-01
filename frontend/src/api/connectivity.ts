/** Lightweight backend reachability probe for production graceful degradation. */

export type BackendReachability =
  | { state: "checking" }
  | { state: "available"; scrapeBusy: boolean }
  | { state: "unavailable"; reason: "not_configured" | "database_unavailable" | "down" | "timeout" };

const PROBE_TIMEOUT_MS = 25_000;

async function fetchWithTimeout(url: string, timeoutMs = PROBE_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { signal: controller.signal, headers: { Accept: "application/json" } });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

type HealthProbeResult =
  | { kind: "ok"; scrapeBusy: boolean }
  | { kind: "database_unavailable" }
  | { kind: "unreachable" };

async function probeHealthEndpoint(): Promise<HealthProbeResult> {
  try {
    const res = await fetchWithTimeout("/health");
    const contentType = res.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) return { kind: "unreachable" };
    const body = (await res.json()) as { status?: string; database?: string; scrape_busy?: boolean };
    if (res.ok && body.status === "ok") {
      return { kind: "ok", scrapeBusy: Boolean(body.scrape_busy) };
    }
    if (body.status === "degraded" && body.database === "unavailable") {
      return { kind: "database_unavailable" };
    }
    return { kind: "unreachable" };
  } catch {
    return { kind: "unreachable" };
  }
}

/** Try /health (Railway + Vercel proxy), then /api/analytics/dataset-summary. */
export async function probeBackendReachability(): Promise<BackendReachability> {
  const health = await probeHealthEndpoint();
  if (health.kind === "ok") return { state: "available", scrapeBusy: health.scrapeBusy };
  if (health.kind === "database_unavailable") {
    return { state: "unavailable", reason: "database_unavailable" };
  }

  try {
    const res = await fetchWithTimeout("/api/analytics/dataset-summary");
    if (res.ok) return { state: "available", scrapeBusy: false };
    if (res.status === 404) return { state: "unavailable", reason: "not_configured" };
    return { state: "unavailable", reason: "down" };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return { state: "unavailable", reason: "timeout" };
    }
    return { state: "unavailable", reason: "down" };
  }
}

/** Lightweight /health poll for scrape_busy (works in local + production). */
export async function probeScrapeBusy(): Promise<boolean> {
  try {
    const res = await fetchWithTimeout("/health", 10_000);
    const contentType = res.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) return false;
    const body = (await res.json()) as { scrape_busy?: boolean };
    return Boolean(body.scrape_busy);
  } catch {
    return false;
  }
}

export function isBackendConnectivityFailure(message: string): boolean {
  return (
    /Požadavek selhal \(404\)/i.test(message) ||
    /Požadavek selhal \(502\)/i.test(message) ||
    /Požadavek selhal \(503\)/i.test(message) ||
    /Požadavek selhal \(504\)/i.test(message) ||
    /Backend neodpovídá/i.test(message) ||
    /Failed to fetch/i.test(message) ||
    /NetworkError/i.test(message)
  );
}
