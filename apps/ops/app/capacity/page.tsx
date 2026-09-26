"use client";

import { useCallback, useState } from "react";
import { PageFrame } from "../../components/PageFrame";
import { CapacityView } from "../../components/views/CapacityView";
import { useOps, useResource } from "../../lib/session";

export default function CapacityPage() {
  const { api } = useOps();
  const [date, setDate] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const resource = useResource(useCallback(() => api.capacity(date || undefined, includeInactive), [api, date, includeInactive]));
  return (
    <PageFrame title="Capacity & workload" description="Configured daily capacity against scheduled jobs per worker (UTC day window)." resource={resource}>
      {(data) => (
        <div className="ops-stack">
          <div className="ops-inline-form">
            <label>Date (UTC)<input type="date" value={date || data.date} onChange={(event) => setDate(event.target.value)} /></label>
            <label className="ops-chip"><input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />Include inactive workers</label>
          </div>
          <CapacityView data={data} />
        </div>
      )}
    </PageFrame>
  );
}
