"use client";

import { useId, useState, type FormEvent } from "react";

export interface ConfirmActionProps {
  label: string;
  title: string;
  description: string;
  confirmLabel?: string;
  tone?: "primary" | "danger";
  /** When set, a reason is required and validated before confirming. */
  reasonLabel?: string;
  validateReason?: (reason: string) => string | null;
  disabled?: boolean;
  onConfirm: (reason: string) => Promise<void>;
}

/**
 * Two-step confirmation for state-changing admin actions. Nothing is sent until the
 * operator confirms, and a failed request keeps the dialog open with the error.
 */
export function ConfirmAction({
  label, title, description, confirmLabel = "Confirm", tone = "primary", reasonLabel, validateReason, disabled, onConfirm,
}: ConfirmActionProps) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const titleId = useId();
  const reasonId = useId();

  async function submit(event: FormEvent) {
    event.preventDefault();
    const problem = reasonLabel && validateReason ? validateReason(reason) : null;
    if (problem) { setError(problem); return; }
    setBusy(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
      setOpen(false);
      setReason("");
    } catch (reasonError) {
      setError(reasonError instanceof Error ? reasonError.message : "The action failed");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button type="button" className={`admin-button admin-button--${tone}`} disabled={disabled} onClick={() => setOpen(true)}>
        {label}
      </button>
    );
  }

  return (
    <form className="admin-confirm" role="alertdialog" aria-labelledby={titleId} onSubmit={submit}>
      <h3 id={titleId}>{title}</h3>
      <p>{description}</p>
      {reasonLabel && (
        <label htmlFor={reasonId}>
          {reasonLabel}
          <textarea id={reasonId} required value={reason} onChange={(event) => setReason(event.target.value)} rows={3} />
        </label>
      )}
      {error && <p className="portal-error" role="alert">{error}</p>}
      <div className="admin-actions">
        <button type="submit" className={`admin-button admin-button--${tone}`} disabled={busy}>
          {busy ? "Working…" : confirmLabel}
        </button>
        <button type="button" className="admin-button" disabled={busy} onClick={() => { setOpen(false); setError(null); }}>
          Cancel
        </button>
      </div>
    </form>
  );
}
