"use client";

import { useCallback, useEffect, useId, useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorState, FormField, LoadingState, Select, ShieldIcon } from "@breero/ui";
import type { MarketplaceMetrics, MetricGroup } from "@breero/types";
import { customerApi } from "@/lib/customer/api";
import {
  GROUP_STATUS_LABEL,
  GROUP_STATUS_VARIANT,
  WINDOW_PRESETS,
  classifyAnalyticsFailure,
  describeMetricValue,
  formatMetricValue,
  formatTimestamp,
  hasNoActivity,
  isStale,
  unavailableGroups,
  windowForPreset,
  type AnalyticsFailure,
  type AnalyticsScope,
  type WindowPresetDays,
} from "./analytics-model";
import styles from "./marketplace-analytics.module.css";

export interface MarketplaceAnalyticsProps {
  scope: AnalyticsScope;
  eyebrow: string;
  title: string;
  description: string;
}

type LoadState =
  | { status: "loading"; data?: MarketplaceMetrics }
  | { status: "ready"; data: MarketplaceMetrics }
  | { status: "failed"; failure: AnalyticsFailure; data?: MarketplaceMetrics };

const STALE_CHECK_INTERVAL_MS = 30_000;

function MetricGroupCard({ group }: { group: MetricGroup }) {
  const headingId = useId();
  return (
    <Card className={styles.groupCard} data-group-status={group.status}>
      <section aria-labelledby={headingId} className={styles.groupBody}>
        <div className={styles.groupHeader}>
          <h3 id={headingId}>{group.label}</h3>
          <Badge variant={GROUP_STATUS_VARIANT[group.status]}>{GROUP_STATUS_LABEL[group.status]}</Badge>
        </div>
        {group.status === "available" ? (
          <dl className={styles.values}>
            {group.values.map((metric) => {
              const detail = describeMetricValue(metric);
              return (
                <div className={styles.valueRow} key={metric.key}>
                  <dt>{metric.label}</dt>
                  <dd>
                    <span className={styles.value}>{formatMetricValue(metric)}</span>
                    {detail && <span className={styles.valueDetail}>{detail}</span>}
                  </dd>
                </div>
              );
            })}
          </dl>
        ) : (
          <div className={styles.withheld}>
            <p>{group.reason}</p>
            {group.blocked_by && <p className={styles.meta}>Waiting on {group.blocked_by}. No value is estimated in the meantime.</p>}
          </div>
        )}
        {group.note && <p className={styles.note}>{group.note}</p>}
        {group.sources.length > 0 && (
          <p className={styles.meta}>
            Source: {group.sources.join(", ")}
            {group.status === "available" && <> · Last source change: {formatTimestamp(group.source_watermark)}</>}
          </p>
        )}
      </section>
    </Card>
  );
}

export function MarketplaceAnalytics({ scope, eyebrow, title, description }: MarketplaceAnalyticsProps) {
  const [preset, setPreset] = useState<WindowPresetDays>(30);
  const [version, setVersion] = useState(0);
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [now, setNow] = useState(() => new Date());
  const windowSelectId = useId();

  const refresh = useCallback(() => setVersion((current) => current + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setState((current) => ({ status: "loading", data: "data" in current ? current.data : undefined }));
    const query = windowForPreset(preset, new Date());
    const load = scope === "marketplace" ? customerApi.analytics.marketplace : customerApi.analytics.provider;
    load(query, controller.signal)
      .then((data) => {
        setNow(new Date());
        setState({ status: "ready", data });
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setState((current) => ({
          status: "failed",
          failure: classifyAnalyticsFailure(reason, scope),
          data: "data" in current ? current.data : undefined,
        }));
      });
    return () => controller.abort();
  }, [scope, preset, version]);

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), STALE_CHECK_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, []);

  const header = (
    <section className="shell market-section">
      <p className="market-eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p>{description}</p>
    </section>
  );

  if (state.status === "failed" && state.failure.kind === "restricted") {
    return (
      <div className="marketplace-page">
        {header}
        <section className="shell market-section">
          <EmptyState title={state.failure.title} description={state.failure.message} />
        </section>
      </div>
    );
  }

  const data = state.data;
  if (!data) {
    return (
      <div className="marketplace-page">
        {header}
        <section className="shell market-section">
          {state.status === "failed" ? (
            <ErrorState title={state.failure.title} description={state.failure.message} onRetry={refresh} />
          ) : (
            <LoadingState label="Loading analytics" />
          )}
        </section>
      </div>
    );
  }

  const stale = isStale(data, now);
  const withheld = unavailableGroups(data);
  const quiet = hasNoActivity(data);
  const refreshing = state.status === "loading";

  return (
    <div className="marketplace-page">
      {header}
      <section className="shell market-section" aria-labelledby="analytics-freshness-title">
        <div className={styles.toolbar}>
          <FormField label="Reporting window" htmlFor={windowSelectId}>
            <Select
              id={windowSelectId}
              value={String(preset)}
              onChange={(event) => setPreset(Number(event.target.value) as WindowPresetDays)}
            >
              {WINDOW_PRESETS.map((option) => (
                <option value={option.days} key={option.days}>{option.label}</option>
              ))}
            </Select>
          </FormField>
          <Button variant="outline" onClick={refresh} loading={refreshing}>Refresh</Button>
        </div>

        <div className={styles.freshness} aria-live="polite">
          <h2 id="analytics-freshness-title" className={styles.srOnly}>Data freshness</h2>
          <p>
            <ShieldIcon size={16} />{" "}
            {data.scope.kind === "marketplace" ? "Marketplace-wide view" : "Your provider organization only"}
          </p>
          <p>Generated {formatTimestamp(data.generated_at)} from one read-only database snapshot.</p>
          <p className={styles.meta}>
            Window {formatTimestamp(data.window.start)} – {formatTimestamp(data.window.end)}
          </p>
          <div className={styles.badges}>
            {stale ? (
              <Badge variant="warning">Stale — older than {Math.round(data.projection.max_age_seconds / 60)} minutes. Refresh to update.</Badge>
            ) : (
              <Badge variant="success">Current</Badge>
            )}
            {withheld.length > 0 && (
              <Badge variant="neutral">{withheld.length} of {data.groups.length} metric groups withheld</Badge>
            )}
            {refreshing && <Badge variant="brand">Refreshing…</Badge>}
          </div>
          {state.status === "failed" && (
            <p role="alert" className={styles.inlineError}>
              {state.failure.title}. Showing the previous result from {formatTimestamp(data.generated_at)}.
            </p>
          )}
        </div>

        {quiet && (
          <EmptyState
            className={styles.quiet}
            title="No recorded activity in this window"
            description="All counts are zero for the selected window. Choose a longer window to compare activity."
          />
        )}

        <div className={styles.groupGrid}>
          {data.groups.map((group) => <MetricGroupCard group={group} key={group.key} />)}
        </div>
      </section>
    </div>
  );
}
