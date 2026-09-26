"use client";

import { useCallback } from "react";
import { PageFrame } from "../../components/PageFrame";
import { ServiceAreasView } from "../../components/views/ServiceAreasView";
import { useOps, useResource } from "../../lib/session";

export default function ServiceAreasPage() {
  const { api } = useOps();
  const resource = useResource(useCallback(() => api.serviceAreas(), [api]));
  return (
    <PageFrame title="Service areas" description="Privacy-safe operational load and coverage per BREERO service zone." resource={resource}>
      {(data) => <ServiceAreasView data={data} />}
    </PageFrame>
  );
}
