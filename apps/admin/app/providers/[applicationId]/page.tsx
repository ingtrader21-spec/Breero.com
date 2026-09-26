"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useState } from "react";
import { PageHeader, useAdmin } from "../../../components/AdminShell";
import { ConfirmAction } from "../../../components/ConfirmAction";
import { ErrorMessage, KeyValues, Loading, Notice, Section, StatusBadge } from "../../../components/ui";
import { formatDateTime } from "../../../lib/format";
import { allowedDecisions, APPLICATION_STATUS_TONE, DECISION_COPY, sectionRows, validateDecisionReason } from "../../../lib/providers";
import type { ProviderApplication } from "../../../lib/types";
import { useResource } from "../../../lib/useResource";

const SECTIONS: { key: keyof ProviderApplication; title: string }[] = [
  { key: "identity", title: "Identity" },
  { key: "business", title: "Business" },
  { key: "contact_details", title: "Contact details" },
  { key: "services", title: "Services" },
  { key: "skills", title: "Skills" },
  { key: "service_areas", title: "Service areas" },
  { key: "postal_codes", title: "Postal codes" },
  { key: "availability", title: "Availability" },
  { key: "capacity", title: "Capacity" },
  { key: "licenses", title: "Licenses" },
  { key: "insurance", title: "Insurance" },
  { key: "compliance_documents", title: "Compliance documents" },
];

export default function ProviderApplicationPage() {
  const params = useParams<{ applicationId: string }>();
  const applicationId = params?.applicationId ?? "";
  const { api } = useAdmin();
  const [override, setOverride] = useState<ProviderApplication | null>(null);
  const loader = useCallback(() => api.getApplication(applicationId), [api, applicationId]);
  const { data, error, loading } = useResource(applicationId ? loader : null);
  const application = override ?? data;
  const decisions = application ? allowedDecisions(application) : [];

  return (
    <>
      <PageHeader eyebrow="Provider applications" title="Application review">
        <p><Link href="/providers">← Review queue</Link></p>
      </PageHeader>
      <Loading active={loading && !application} />
      <ErrorMessage error={error} />
      {application && (
        <>
          <Section title="Decision">
            <KeyValues rows={[
              { label: "Status", value: <StatusBadge value={application.status} tone={APPLICATION_STATUS_TONE[application.status]} /> },
              { label: "Submitted", value: formatDateTime(application.submitted_at) },
              { label: "Decided", value: formatDateTime(application.decided_at) },
              { label: "Version", value: String(application.version) },
              { label: "Vendor ID", value: application.vendor_id },
            ]} />
            {application.decision_reason && <Notice title="Decision reason">{application.decision_reason}</Notice>}
            {application.requested_information && <Notice tone="warning" title="Information requested">{application.requested_information}</Notice>}
            {decisions.length === 0 && <Notice>No decision is available: applications can only be decided while pending review.</Notice>}
            <div className="admin-actions">
              {decisions.map((decision) => (
                <ConfirmAction
                  key={decision}
                  label={DECISION_COPY[decision].label}
                  title={`${DECISION_COPY[decision].label} this application?`}
                  description={DECISION_COPY[decision].confirm}
                  confirmLabel={DECISION_COPY[decision].label}
                  tone={decision === "reject" ? "danger" : "primary"}
                  reasonLabel={DECISION_COPY[decision].reasonLabel}
                  validateReason={validateDecisionReason}
                  onConfirm={async (reason) => setOverride(await api.decideApplication(application.id, decision, reason))}
                />
              ))}
            </div>
          </Section>
          {SECTIONS.map(({ key, title }) => {
            const rows = sectionRows(application[key]);
            return (
              <Section key={key} title={title}>
                {rows.length ? <KeyValues rows={rows} /> : <p className="portal-empty">Not provided.</p>}
              </Section>
            );
          })}
        </>
      )}
    </>
  );
}
