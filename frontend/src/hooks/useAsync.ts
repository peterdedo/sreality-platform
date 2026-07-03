import { useEffect, useState } from "react";
import { readQueryCache, writeQueryCache } from "./queryCache";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  refreshing: boolean;
  error: Error | null;
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    loading: true,
    refreshing: false,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({
      ...s,
      loading: s.data === null,
      refreshing: s.data !== null,
      error: null,
    }));

    fn()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, refreshing: false, error: null });
      })
      .catch((error) => {
        if (!cancelled) {
          setState((s) => ({
            data: s.data,
            loading: false,
            refreshing: false,
            error: error instanceof Error ? error : new Error(String(error)),
          }));
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}

/** Cached fetch — reuses recent response when navigating between pages. */
export function useCachedAsync<T>(
  cacheKey: string,
  fn: () => Promise<T>,
  deps: unknown[],
  ttlMs = 20_000
): AsyncState<T> {
  const cached = readQueryCache<T>(cacheKey);
  const [state, setState] = useState<AsyncState<T>>({
    data: cached,
    loading: cached === null,
    refreshing: false,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    const hit = readQueryCache<T>(cacheKey);
    if (hit) {
      setState({ data: hit, loading: false, refreshing: true, error: null });
    } else {
      setState((s) => ({ ...s, loading: s.data === null, refreshing: s.data !== null, error: null }));
    }

    fn()
      .then((data) => {
        if (cancelled) return;
        writeQueryCache(cacheKey, data, ttlMs);
        setState({ data, loading: false, refreshing: false, error: null });
      })
      .catch((error) => {
        if (cancelled) return;
        setState((s) => ({
          data: s.data,
          loading: false,
          refreshing: false,
          error: error instanceof Error ? error : new Error(String(error)),
        }));
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
