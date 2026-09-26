"use client";

import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../lib/api";
import { errorMessage } from "../lib/format";
import type { Tone } from "../lib/onboarding";

export function StatusBadge({ label, tone }: { label: string; tone: Tone }) {
  return <span className={`partner-badge partner-badge--${tone}`}>{label}</span>;
}

export function Alert({ tone = "danger", children }: { tone?: Tone; children: ReactNode }) {
  if (!children) return null;
  return (
    <p className={`partner-alert partner-alert--${tone}`} role={tone === "danger" ? "alert" : "status"}>
      {children}
    </p>
  );
}

export function Loading({ label = "Loading live data…" }: { label?: string }) {
  return <p role="status" className="partner-muted">{label}</p>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="portal-empty">{children}</p>;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="partner-field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function Panel({ title, description, actions, children }: { title: string; description?: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="portal-panel partner-panel" aria-label={title}>
      <div className="partner-panel__head">
        <div>
          <h2>{title}</h2>
          {description && <p className="partner-muted">{description}</p>}
        </div>
        {actions && <div className="partner-actions">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

export interface Resource<T> {
  data: T | null;
  error: string;
  loading: boolean;
  reload: () => Promise<void>;
}

/** Loads live data; `load` must be referentially stable (wrap it in useCallback). */
export function useResource<T>(load: () => Promise<T>): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);

  const reload = useCallback(async () => {
    const current = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const next = await load();
      if (current === generation.current) setData(next);
    } catch (reason) {
      if (current === generation.current) setError(errorMessage(reason, "Unable to load data"));
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }, [load]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload };
}

export interface Action {
  busy: boolean;
  error: string;
  notice: string;
  run: (task: () => Promise<unknown>, success?: string) => Promise<boolean>;
  clear: () => void;
}

/** Serializes user-triggered mutations and surfaces their outcome. */
export function useAction(): Action {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const run = useCallback(async (task: () => Promise<unknown>, success = "") => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await task();
      setNotice(success);
      return true;
    } catch (reason) {
      const conflict = reason instanceof ApiError && reason.isVersionConflict;
      setError(
        conflict
          ? "This record changed since you loaded it. It has been refreshed — review and try again."
          : errorMessage(reason),
      );
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  const clear = useCallback(() => {
    setError("");
    setNotice("");
  }, []);

  return { busy, error, notice, run, clear };
}
