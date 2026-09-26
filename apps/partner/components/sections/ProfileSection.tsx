"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { labelize } from "../../lib/format";
import type { ProviderProfile, ProviderProfilePatch } from "../../lib/types";
import type { SectionProps } from "../PartnerApp";
import { Alert, Field, Loading, Panel, StatusBadge, useAction, useResource } from "../ui";

interface ProfileForm { legalName: string; displayName: string; phone: string; radiusMiles: string }

const METERS_PER_MILE = 1609.344;

export function profileForm(profile: ProviderProfile): ProfileForm {
  return {
    legalName: profile.legal_name,
    displayName: profile.display_name,
    phone: profile.phone,
    radiusMiles: String(Math.round(profile.service_radius_meters / METERS_PER_MILE)),
  };
}

/** Only changed fields are sent; the API validates 1–500 km of service radius. */
export function profilePatch(form: ProfileForm, profile: ProviderProfile): { patch: ProviderProfilePatch; errors: string[] } {
  const errors: string[] = [];
  const patch: ProviderProfilePatch = {};
  const legalName = form.legalName.trim();
  const displayName = form.displayName.trim();
  const phone = form.phone.trim();
  if (!legalName) errors.push("Legal name is required.");
  if (!displayName) errors.push("Display name is required.");
  if (phone.length < 5) errors.push("Enter a reachable phone number.");
  const miles = Number(form.radiusMiles);
  const meters = Math.round(miles * METERS_PER_MILE);
  if (!Number.isFinite(miles) || meters < 1000 || meters > 500000) errors.push("Service radius must be between 1 and 310 miles.");
  if (legalName !== profile.legal_name) patch.legal_name = legalName;
  if (displayName !== profile.display_name) patch.display_name = displayName;
  if (phone !== profile.phone) patch.phone = phone;
  if (String(Math.round(profile.service_radius_meters / METERS_PER_MILE)) !== form.radiusMiles.trim()) patch.service_radius_meters = meters;
  return { patch, errors };
}

export function ProfileSection({ api }: SectionProps) {
  const load = useCallback(() => api.profile(), [api]);
  const resource = useResource(load);
  const action = useAction();
  const [form, setForm] = useState<ProfileForm | null>(null);
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    if (resource.data) setForm(profileForm(resource.data));
  }, [resource.data]);

  if (resource.loading && !resource.data) return <Loading />;
  if (resource.error && !resource.data) return <Alert>{resource.error}</Alert>;
  if (!resource.data || !form) return null;
  const profile = resource.data;
  const editable = profile.status !== "SUSPENDED" && profile.status !== "REJECTED";

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    const result = profilePatch(form, profile);
    setErrors(result.errors);
    if (result.errors.length) return;
    if (Object.keys(result.patch).length === 0) return;
    await action.run(() => api.updateProfile(result.patch), "Company profile saved.");
    await resource.reload();
  }

  return (
    <Panel
      title="Company profile"
      description="Public name, legal entity, contact phone, and travel radius for your organization."
      actions={<StatusBadge label={labelize(profile.status)} tone={profile.status === "ACTIVE" ? "success" : profile.status === "PENDING" ? "info" : "danger"} />}
    >
      <Alert>{errors.join(" ")}</Alert>
      <Alert>{action.error}</Alert>
      <Alert tone="success">{action.notice}</Alert>
      <form className="partner-form" onSubmit={(event) => void save(event)}>
        <div className="partner-grid">
          <Field label="Legal name"><input value={form.legalName} disabled={!editable} onChange={(e) => setForm({ ...form, legalName: e.target.value })} /></Field>
          <Field label="Display name"><input value={form.displayName} disabled={!editable} onChange={(e) => setForm({ ...form, displayName: e.target.value })} /></Field>
          <Field label="Account email" hint="Managed through your BREERO sign-in."><input value={profile.email} disabled readOnly /></Field>
          <Field label="Phone"><input type="tel" value={form.phone} disabled={!editable} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
          <Field label="Service radius (miles)"><input inputMode="numeric" value={form.radiusMiles} disabled={!editable} onChange={(e) => setForm({ ...form, radiusMiles: e.target.value })} /></Field>
        </div>
        {editable ? (
          <div className="partner-actions"><button type="submit" className="partner-button" disabled={action.busy}>Save profile</button></div>
        ) : (
          <Alert tone="warning">This organization cannot be edited in its current state.</Alert>
        )}
      </form>
    </Panel>
  );
}
