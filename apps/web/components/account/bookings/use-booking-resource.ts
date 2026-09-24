"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, type ApiErrorKind } from "@breero/api-client";
import { safeCustomerError } from "@/lib/customer/errors";

type Failure = { kind: ApiErrorKind; message: string };

// Keep booking reads scoped to the current loader. Aborting alone does not
// prevent a late response from adapters that have already resolved a request.
export function useBookingResource<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{
    load: typeof load; attempt: number; value?: T; error?: Failure;
  }>();
  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal).then((value) => {
      if (!controller.signal.aborted) setResult({ load, attempt, value });
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setResult({ load, attempt, error: {
        kind: reason instanceof ApiError ? reason.kind : "unknown",
        message: safeCustomerError(reason).message,
      } });
    });
    return () => controller.abort();
  }, [load, attempt]);
  const current = result?.load === load && result.attempt === attempt ? result : undefined;
  return { value: current?.value, error: current?.error, retry,
    replace: (value: T) => setResult({ load, attempt, value }),
  };
}
