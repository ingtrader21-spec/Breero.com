"use client";

import { useCallback } from "react";
import { PageFrame } from "../components/PageFrame";
import { DashboardView } from "../components/views/DashboardView";
import { useOps, useResource } from "../lib/session";

export default function DashboardPage() {
  const { api } = useOps();
  const resource = useResource(useCallback(() => api.dashboard(), [api]));
  return (
    <PageFrame title="Operations dashboard" description="Live job, SLA, workforce and integration health from the canonical API." resource={resource}>
      {(data) => <DashboardView data={data} />}
    </PageFrame>
  );
}
