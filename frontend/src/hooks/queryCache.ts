type Entry = { data: unknown; expiresAt: number };

const store = new Map<string, Entry>();

export function readQueryCache<T>(key: string): T | null {
  const entry = store.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    store.delete(key);
    return null;
  }
  return entry.data as T;
}

export function writeQueryCache(key: string, data: unknown, ttlMs: number) {
  store.set(key, { data, expiresAt: Date.now() + ttlMs });
}

export function invalidateQueryCache(key: string) {
  store.delete(key);
}
