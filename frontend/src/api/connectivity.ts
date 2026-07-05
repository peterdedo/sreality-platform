/** Lightweight backend reachability probe for production graceful degradation. */

export type BackendReachability =
  | { state: "checking" }
  | { state: "available" }
  | { state: "unavailable"; reason: "not_configured" | "down" | "timeout" };

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

async function probeHealthEndpoint(): Promise<boolean> {
  try {
    const res = await fetchWithTimeout("/health");
    if (!res.ok) return false;
    const contentType = res.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) return false;
    const body = (await res.json()) as { status?: string };
    return body.status === "ok";
  } catch {
    return false;
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
  if (await probeHealthEndpoint()) {
    return { state: "available" };
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
