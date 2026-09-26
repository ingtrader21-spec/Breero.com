"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useMemo } from "react";
import { PageFrame } from "../../components/PageFrame";
import { Loading } from "../../components/ui";
import { JobTable } from "../../components/views/JobTable";
import { QueueFilters } from "../../components/views/QueueFilters";
import { fromSearchParams, toQueueSearchParams, type QueueFilterState } from "../../lib/queue-filters";
import { useOps, useResource } from "../../lib/session";

function DispatchQueue() {
  const { api } = useOps();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const query = searchParams.toString();
  const filters = useMemo(() => fromSearchParams(new URLSearchParams(query)), [query]);
  const resource = useResource(useCallback(() => api.queue(filters), [api, filters]));

  const apply = useCallback(
    (next: QueueFilterState) => {
      const params = toQueueSearchParams(next);
      router.replace(`${pathname}?${params.toString()}`);
    },
    [pathname, router],
  );

  return (
    <PageFrame title="Dispatch queue" description="Active jobs ordered by scheduled start, with server-evaluated SLA risk." resource={resource}>
      {(page) => (
        <div className="ops-stack">
          <QueueFilters key={query} initial={filters} onApply={apply} />
          {page.scan_truncated && <p className="ops-notice">At-risk filtering covered the earliest-scheduled active jobs only; the scan limit was reached.</p>}
          <JobTable items={page.items} generatedAt={page.generated_at} emptyMessage="No jobs match these filters." />
          <nav className="ops-pager" aria-label="Queue pages">
            <span>{page.total === 0 ? "0 jobs" : `${page.offset + 1}–${page.offset + page.items.length} of ${page.total}`}</span>
            <button type="button" className="ops-button ops-button--ghost" disabled={page.offset === 0} onClick={() => apply({ ...filters, offset: Math.max(page.offset - page.limit, 0) })}>Previous</button>
            <button type="button" className="ops-button ops-button--ghost" disabled={page.offset + page.items.length >= page.total} onClick={() => apply({ ...filters, offset: page.offset + page.limit })}>Next</button>
          </nav>
        </div>
      )}
    </PageFrame>
  );
}

export default function QueuePage() {
  return <Suspense fallback={<Loading />}><DispatchQueue /></Suspense>;
}
