import { useCallback, useEffect, useRef, useState } from 'react';
import { getErrorMessage } from './errors';

export function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}

interface AsyncState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * Runs `loader` whenever `deps` change; ignores stale responses.
 * Pass `enabled=false` to skip (e.g. no doctor selected yet).
 */
export function useAsync<T>(loader: () => Promise<T>, deps: readonly unknown[], enabled = true): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }
    let stale = false;
    setIsLoading(true);
    setError(null);
    loaderRef
      .current()
      .then((result) => !stale && setData(result))
      .catch((err: unknown) => !stale && setError(getErrorMessage(err)))
      .finally(() => !stale && setIsLoading(false));
    return () => {
      stale = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, isLoading, error, reload };
}
