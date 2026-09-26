"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { OpsApi } from "./api";
import type { OpsSession } from "./types";

export interface OpsContextValue {
  session: OpsSession;
  api: OpsApi;
  signOut: () => void;
}

export const OpsContext = createContext<OpsContextValue | null>(null);

export function useOps(): OpsContextValue {
  const value = useContext(OpsContext);
  if (!value) throw new Error("useOps must be used inside the operations shell");
  return value;
}

export function errorMessage(reason: unknown, fallback = "Unable to load data"): string {
  return reason instanceof Error && reason.message ? reason.message : fallback;
}

export interface Resource<T> {
  data?: T;
  error?: string;
  loading: boolean;
  reload: () => void;
}

/** Load server data for a view. `loader` must be memoized by the caller. */
export function useResource<T>(loader: () => Promise<T>): Resource<T> {
  const [state, setState] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: true });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let active = true;
    setState((previous) => ({ data: previous.data, loading: true }));
    loader().then(
      (data) => { if (active) setState({ data, loading: false }); },
      (reason: unknown) => { if (active) setState((previous) => ({ data: previous.data, loading: false, error: errorMessage(reason) })); },
    );
    return () => { active = false; };
  }, [loader, nonce]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);
  return { ...state, reload };
}
