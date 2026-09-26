"use client";

import { useCallback, useEffect, useState } from "react";

export interface Resource<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/** Loads `loader` whenever its identity changes; wrap it in useCallback at the call site. */
export function useResource<T>(loader: (() => Promise<T>) | null): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!loader) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    loader()
      .then((value) => { if (!cancelled) setData(value); })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Unable to load data"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [loader, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { data, error, loading, reload };
}
