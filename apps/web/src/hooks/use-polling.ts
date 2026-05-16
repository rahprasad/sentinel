"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Generic polling hook. Calls `fetcher` every `intervalMs` and returns
 * the latest result, loading state, and error.
 */
export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const poll = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    poll();

    const id = setInterval(poll, intervalMs);
    return () => clearInterval(id);
  }, [poll, intervalMs]);

  return { data, error, loading, refetch: poll };
}
