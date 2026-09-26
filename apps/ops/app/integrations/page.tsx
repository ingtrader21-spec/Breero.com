"use client";

import { useCallback } from "react";
import { PageFrame } from "../../components/PageFrame";
import { IntegrationFailuresView } from "../../components/views/IntegrationFailuresView";
import { useOps, useResource } from "../../lib/session";

export default function IntegrationsPage() {
  const { api } = useOps();
  const resource = useResource(useCallback(() => api.integrationFailures(), [api]));
  return (
    <PageFrame title="Integration failures" description="Durable outbox deliveries that failed or await configuration." resource={resource}>
      {(data) => <IntegrationFailuresView data={data} />}
    </PageFrame>
  );
}
