"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useState } from "react";
import { PageFrame } from "../../../components/PageFrame";
import { DispatchPanel } from "../../../components/views/DispatchPanel";
import { JobDetailView, WorkRequestList } from "../../../components/views/JobDetailView";
import { TransitionPanel } from "../../../components/views/TransitionPanel";
import { STATUS_LABELS } from "../../../lib/format";
import { errorMessage, useOps, useResource } from "../../../lib/session";
import type { AssignmentCandidate, JobStatus } from "../../../lib/types";

type Feedback = { tone: "ok" | "error"; message: string } | null;

export default function JobPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const { api } = useOps();
  const detail = useResource(useCallback(() => api.jobDetail(jobId), [api, jobId]));
  const dispatchable = Boolean(detail.data && (detail.data.actions.can_assign || detail.data.actions.can_reassign));
  const candidates = useResource(
    useCallback(() => (dispatchable ? api.candidates(jobId) : Promise.resolve(undefined)), [api, jobId, dispatchable]),
  );
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const reloadDetail = detail.reload;
  const reloadCandidates = candidates.reload;

  // Every mutation is followed by a server readback; the UI never patches state locally.
  const run = useCallback(
    async (label: string, action: () => Promise<string>) => {
      setBusy(true);
      setFeedback(null);
      try {
        setFeedback({ tone: "ok", message: await action() });
      } catch (reason) {
        setFeedback({ tone: "error", message: errorMessage(reason, `${label} failed`) });
      } finally {
        setBusy(false);
        reloadDetail();
        reloadCandidates();
      }
    },
    [reloadDetail, reloadCandidates],
  );

  const onMatch = () =>
    run("Matching", async () => {
      const offers = await api.match(jobId);
      return offers.length ? `Matching created ${offers.length} offer(s).` : "Matching found no dispatchable candidates.";
    });
  const onAssign = (candidate: AssignmentCandidate, reason: string) =>
    run("Assignment", async () => {
      await api.assign(jobId, { vendor_id: candidate.vendor_id, worker_id: candidate.worker_id, reason });
      return `Assigned to ${candidate.worker_name}.`;
    });
  const onReassign = (candidate: AssignmentCandidate, reason: string, expectedVersion: number) =>
    run("Reassignment", async () => {
      const result = await api.reassign(jobId, { vendor_id: candidate.vendor_id, worker_id: candidate.worker_id, reason, expected_version: expectedVersion });
      return `Reassigned to ${candidate.worker_name}; job is now version ${result.job_version}.`;
    });
  const onTransition = (status: JobStatus, reason: string) =>
    run("Transition", async () => {
      const result = await api.transition(jobId, status, reason);
      return `Job moved to ${STATUS_LABELS[result.status]}.`;
    });
  const onReview = (requestId: string, approve: boolean) =>
    run("Work request review", async () => {
      const result = await api.reviewWorkRequest(requestId, approve);
      return approve ? `Work request sent to the customer (${result.status}).` : "Work request declined.";
    });

  return (
    <PageFrame title="Job control" description="Timeline, dispatch, lifecycle and work-request review for one job." resource={detail}>
      {(data) => (
        <div className="ops-stack">
          <Link href="/queue" className="ops-link">← Back to dispatch queue</Link>
          {feedback && <p className={feedback.tone === "ok" ? "ops-success" : "ops-error"} role={feedback.tone === "ok" ? "status" : "alert"}>{feedback.message}</p>}
          <JobDetailView
            detail={data}
            actions={
              <div className="ops-stack">
                <DispatchPanel
                  key={`dispatch-${data.job.version}`}
                  actions={data.actions}
                  candidates={candidates.data}
                  candidatesError={candidates.error}
                  busy={busy}
                  onMatch={onMatch}
                  onAssign={onAssign}
                  onReassign={onReassign}
                />
                <TransitionPanel
                  key={`transition-${data.job.version}`}
                  allowed={data.actions.allowed_transitions}
                  technicianCommands={data.actions.technician_commands}
                  busy={busy}
                  onTransition={onTransition}
                />
                <WorkRequestList detail={data} busy={busy} onReview={onReview} />
              </div>
            }
          />
        </div>
      )}
    </PageFrame>
  );
}
