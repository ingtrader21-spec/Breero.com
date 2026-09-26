"use client";

import { useCallback, useState } from "react";
import { PageFrame } from "../../components/PageFrame";
import { ExceptionsView } from "../../components/views/ExceptionsView";
import { SEVERITY_LABELS } from "../../lib/format";
import { useOps, useResource } from "../../lib/session";
import { RISK_SEVERITIES, type RiskSeverity } from "../../lib/types";

export default function ExceptionsPage() {
  const { api } = useOps();
  const [severity, setSeverity] = useState<RiskSeverity | "">("");
  const resource = useResource(useCallback(() => api.exceptions(severity || undefined), [api, severity]));
  return (
    <PageFrame title="SLA & exception queue" description="Active jobs breaching the server-side operations policy, most severe first." resource={resource}>
      {(data) => (
        <div className="ops-stack">
          <label className="ops-inline-field">Severity
            <select value={severity} onChange={(event) => setSeverity(event.target.value as RiskSeverity | "")}>
              <option value="">All findings</option>
              {RISK_SEVERITIES.map((level) => <option key={level} value={level}>{SEVERITY_LABELS[level]}</option>)}
            </select>
          </label>
          <ExceptionsView data={data} />
        </div>
      )}
    </PageFrame>
  );
}
