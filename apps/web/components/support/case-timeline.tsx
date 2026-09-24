import { Badge, Card, EmptyState } from "@breero/ui";
import {
  audiencePresentation,
  caseStatusLabel,
  effectiveAudience,
  escalationLabel,
  evidencePresentation,
  visibleCaseEntries,
  type SupportCaseEntry,
  type SupportViewer,
} from "@/lib/support/case-model";
import styles from "./support-case.module.css";

export interface CaseTimelineProps {
  viewer: SupportViewer;
  entries: readonly SupportCaseEntry[];
}

function EntryContent({ entry }: { entry: SupportCaseEntry }) {
  if (entry.kind === "evidence") {
    if (!entry.evidence) return <p className={styles.entryBody}>Evidence details are unavailable.</p>;
    const evidence = evidencePresentation(entry.evidence.scan_state);
    return (
      <div className={styles.meta}>
        <span>{entry.evidence.file_name}</span>
        <Badge variant={evidence.variant}>{evidence.label}</Badge>
        {!evidence.downloadable && <span>Download is blocked until the file is scanned clean.</span>}
      </div>
    );
  }
  if (entry.kind === "status_change") {
    if (!entry.status_change) return <p className={styles.entryBody}>Status details are unavailable.</p>;
    return (
      <p className={styles.entryBody}>
        Status changed from {caseStatusLabel(entry.status_change.from)} to {caseStatusLabel(entry.status_change.to)}.
      </p>
    );
  }
  if (entry.kind === "escalation") {
    if (!entry.escalation) return <p className={styles.entryBody}>Escalation details are unavailable.</p>;
    return (
      <p className={styles.entryBody}>
        Escalated to {escalationLabel(entry.escalation.level)}: {entry.escalation.reason}
      </p>
    );
  }
  return <p className={styles.entryBody}>{entry.body ?? ""}</p>;
}

const KIND_TITLES: Record<SupportCaseEntry["kind"], string> = {
  message: "Message",
  internal_note: "Internal note",
  evidence: "Evidence",
  status_change: "Status change",
  escalation: "Escalation",
};

/**
 * Case activity rendered through the fail-closed visibility policy. Entries the
 * viewer may not see are removed before rendering, not hidden with CSS.
 */
export function CaseTimeline({ viewer, entries }: CaseTimelineProps) {
  const visible = visibleCaseEntries(viewer, entries);
  if (visible.length === 0) {
    return <EmptyState title="No case activity to show" description="There is no activity on this case that you are allowed to see." />;
  }
  return (
    <ol className={styles.timeline} aria-label="Case activity">
      {visible.map((entry) => {
        const audience = effectiveAudience(entry) ?? "internal";
        const presentation = audiencePresentation(audience);
        return (
          <li key={entry.id}>
            <Card className={audience === "internal" ? `${styles.entry} ${styles.internal}` : styles.entry}>
              <div className={styles.entryHeader}>
                <strong>{KIND_TITLES[entry.kind]}</strong>
                <Badge variant={presentation.variant}>{presentation.label}</Badge>
              </div>
              <EntryContent entry={entry} />
              <div className={styles.meta}>
                <span>{entry.author_label}</span>
                <time dateTime={entry.occurred_at}>{entry.occurred_at}</time>
              </div>
            </Card>
          </li>
        );
      })}
    </ol>
  );
}
