"use client";

import type { HTMLAttributes, ReactNode } from "react";
import { Badge, Card } from "./primitives";
import { cx } from "./utils";

export type PricingMode = "instant_bookable" | "quote_required" | "request_only";
export type CapacityState = "available" | "limited" | "manual_review" | "unavailable";
export type TrustKind = "identity" | "business" | "license" | "insurance" | "background" | "service";
export type TrustStatus = "verified" | "pending" | "expired" | "not_required";
export type TimelineStepStatus = "complete" | "current" | "upcoming" | "blocked";
export type MarketplaceState = "loading" | "empty" | "error" | "restricted" | "disabled" | "success";

const pricingLabels: Record<PricingMode, string> = {
  instant_bookable: "Instant booking",
  quote_required: "Quote required",
  request_only: "Request only",
};

const capacityLabels: Record<CapacityState, string> = {
  available: "Capacity available",
  limited: "Limited capacity",
  manual_review: "Dispatcher review",
  unavailable: "No capacity",
};

const trustLabels: Record<TrustKind, string> = {
  identity: "Identity",
  business: "Business",
  license: "License",
  insurance: "Insurance",
  background: "Background screening",
  service: "Service qualification",
};

const trustStatusLabels: Record<TrustStatus, string> = {
  verified: "Verified",
  pending: "Pending review",
  expired: "Expired",
  not_required: "Not required",
};

export function PricingModeBadge({ mode, className }: { mode: PricingMode; className?: string }) {
  const variant = mode === "instant_bookable" ? "success" : mode === "quote_required" ? "brand" : "neutral";
  return <Badge className={cx("br-pricing-mode", `br-pricing-mode--${mode}`, className)} variant={variant}>{pricingLabels[mode]}</Badge>;
}

export function CapacitySignal({ state, detail, className }: { state: CapacityState; detail?: string; className?: string }) {
  return (
    <div className={cx("br-capacity-signal", `br-capacity-signal--${state}`, className)} role="status" data-state={state}>
      <span className="br-capacity-signal__dot" aria-hidden="true" />
      <span><strong>{capacityLabels[state]}</strong>{detail && <small>{detail}</small>}</span>
    </div>
  );
}

export function TrustBadge({ kind, status, label, className }: { kind: TrustKind; status: TrustStatus; label?: string; className?: string }) {
  return (
    <span className={cx("br-trust-badge", `br-trust-badge--${status}`, className)} data-status={status}>
      <span className="br-trust-badge__mark" aria-hidden="true">{status === "verified" ? "✓" : status === "expired" ? "!" : "•"}</span>
      <span><strong>{label ?? trustLabels[kind]}</strong><small>{trustStatusLabels[status]}</small></span>
    </span>
  );
}

export type MarketplaceServiceCardProps = {
  title: string;
  description: string;
  href: string;
  category?: string;
  pricingMode: PricingMode;
  durationLabel?: string;
  coverageLabel?: string;
  emergencyEligible?: boolean;
  actionLabel?: string;
  icon?: ReactNode;
  className?: string;
};

export function MarketplaceServiceCard({
  title,
  description,
  href,
  category,
  pricingMode,
  durationLabel,
  coverageLabel,
  emergencyEligible,
  actionLabel = "View service",
  icon,
  className,
}: MarketplaceServiceCardProps) {
  return (
    <Card interactive className={cx("br-marketplace-service", className)}>
      <article>
        <div className="br-marketplace-service__topline">
          {icon && <span className="br-marketplace-service__icon" aria-hidden="true">{icon}</span>}
          <div className="br-marketplace-service__badges">
            <PricingModeBadge mode={pricingMode} />
            {emergencyEligible && <Badge variant="warning">Emergency eligible</Badge>}
          </div>
        </div>
        {category && <p className="br-marketplace-service__category">{category}</p>}
        <h3>{title}</h3>
        <p className="br-marketplace-service__description">{description}</p>
        {(durationLabel || coverageLabel) && <dl className="br-marketplace-service__facts">
          {durationLabel && <div><dt>Typical duration</dt><dd>{durationLabel}</dd></div>}
          {coverageLabel && <div><dt>Coverage</dt><dd>{coverageLabel}</dd></div>}
        </dl>}
        <a className="br-marketplace-service__link" href={href}>{actionLabel}<span aria-hidden="true">→</span></a>
      </article>
    </Card>
  );
}

export type ProviderTrustFact = {
  kind: TrustKind;
  status: TrustStatus;
  label?: string;
};

export type ProviderTrustCardProps = {
  providerName: string;
  summary?: string;
  trust: ProviderTrustFact[];
  rating?: number;
  reviewCount?: number;
  coverage?: string;
  responseTime?: string;
  capacity?: CapacityState;
  capacityDetail?: string;
  action?: ReactNode;
  className?: string;
};

export function ProviderTrustCard({
  providerName,
  summary,
  trust,
  rating,
  reviewCount,
  coverage,
  responseTime,
  capacity,
  capacityDetail,
  action,
  className,
}: ProviderTrustCardProps) {
  const showRating = typeof rating === "number" && Number.isFinite(rating) && rating >= 1 && rating <= 5
    && typeof reviewCount === "number" && Number.isInteger(reviewCount) && reviewCount > 0;
  return (
    <Card className={cx("br-provider-trust-card", className)}>
      <article>
        <header className="br-provider-trust-card__header">
          <div><p className="br-provider-trust-card__eyebrow">Provider profile</p><h3>{providerName}</h3></div>
          {showRating && <p className="br-provider-trust-card__rating" aria-label={`${rating} out of 5 from ${reviewCount} verified service reviews`}><strong>{rating?.toFixed(1)}</strong><span>★</span><small>{reviewCount} reviews</small></p>}
        </header>
        {summary && <p className="br-provider-trust-card__summary">{summary}</p>}
        <div className="br-provider-trust-card__trust" aria-label="Verification status">
          {trust.map((fact) => <TrustBadge key={`${fact.kind}-${fact.label ?? "default"}`} {...fact} />)}
        </div>
        {(coverage || responseTime) && <dl className="br-provider-trust-card__facts">
          {coverage && <div><dt>Service coverage</dt><dd>{coverage}</dd></div>}
          {responseTime && <div><dt>Typical response</dt><dd>{responseTime}</dd></div>}
        </dl>}
        {capacity && <CapacitySignal state={capacity} detail={capacityDetail} />}
        {action && <div className="br-provider-trust-card__action">{action}</div>}
      </article>
    </Card>
  );
}

export type ProjectTimelineStep = {
  id: string;
  label: string;
  description?: string;
  status: TimelineStepStatus;
  timestamp?: string;
};

export function ProjectStatusTimeline({ steps, label = "Project progress", className }: { steps: ProjectTimelineStep[]; label?: string; className?: string }) {
  const currentIndex = steps.findIndex((step) => step.status === "current");
  return (
    <ol className={cx("br-project-timeline", className)} aria-label={label}>
      {steps.map((step, index) => {
        const status = step.status === "current" && index !== currentIndex ? "upcoming" : step.status;
        return <li key={step.id} className={cx("br-project-timeline__step", `br-project-timeline__step--${status}`)} aria-current={status === "current" ? "step" : undefined}>
          <span className="br-project-timeline__marker" aria-hidden="true">{status === "complete" ? "✓" : ""}</span>
          <div><strong>{step.label}</strong>{step.description && <p>{step.description}</p>}{step.timestamp && <time>{step.timestamp}</time>}</div>
        </li>;
      })}
    </ol>
  );
}

export function MarketplaceStatePanel({
  state,
  title,
  description,
  action,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement> & { state: MarketplaceState; title: string; description: string; action?: ReactNode }) {
  const role = state === "error" ? "alert" : "status";
  return (
    <div className={cx("br-marketplace-state", `br-marketplace-state--${state}`, className)} role={role} data-state={state} {...props}>
      <span className="br-marketplace-state__icon" aria-hidden="true">{state === "success" ? "✓" : state === "error" ? "!" : state === "loading" ? "…" : "•"}</span>
      <div><h3>{title}</h3><p>{description}</p>{action && <div className="br-marketplace-state__action">{action}</div>}</div>
    </div>
  );
}
