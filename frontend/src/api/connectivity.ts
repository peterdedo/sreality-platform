/** Lightweight backend reachability probe for production graceful degradation. */

export type BackendReachability =
  | { state: "checking" }
  | { state: "available" }
  | { state: "unavailable"; reason: "not_configured" | "database_unavailable" | "down" | "timeout" };

const PROBE_TIMEOUT_MS = 8_000;

async function fetchWithTimeout(url: string, timeoutMs = PROBE_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { signal: controller.signal, headers: { Accept: "application/json" } });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

async function probeHealthEndpoint(): Promise<"ok" | "database_unavailable" | "unreachable"> {
  try {
    const res = await fetchWithTimeout("/health");
    const contentType = res.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) return "unreachable";
    const body = (await res.json()) as { status?: string; database?: string };
    if (res.ok && body.status === "ok") return "ok";
    if (body.status === "degraded" && body.database === "unavailable") {
      return "database_unavailable";
    }
    return "unreachable";
  } catch {
    return "unreachable";
  }
}

async function probeDatasetSummary(): Promise<boolean> {
  try {
    const res = await fetchWithTimeout("/api/analytics/dataset-summary");
    return res.ok;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return false;
    return false;
  }
}

/** Try /health (Railway + Vercel proxy), then /api/analytics/dataset-summary. */
export async function probeBackendReachability(): Promise<BackendReachability> {
  const health = await probeHealthEndpoint();
  if (health === "ok") return { state: "available" };
  if (health === "database_unavailable") {
    return { state: "unavailable", reason: "database_unavailable" };
  }

  try {
    const res = await fetchWithTimeout("/api/analytics/dataset-summary");
    if (res.ok) return { state: "available" };
    if (res.status === 404) return { state: "unavailable", reason: "not_configured" };
    return { state: "unavailable", reason: "down" };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return { state: "unavailable", reason: "timeout" };
    }
    return { state: "unavailable", reason: "down" };
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
