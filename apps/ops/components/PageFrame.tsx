"use client";

import type { ReactNode } from "react";
import type { Resource } from "../lib/session";
import { ErrorBanner, Freshness, Loading } from "./ui";

/** Standard page chrome: title, server freshness, loading and error states. */
export function PageFrame<T extends { generated_at: string }>({
  title,
  description,
  resource,
  children,
}: {
  title: string;
  description: string;
  resource: Resource<T>;
  children: (data: T) => ReactNode;
}) {
  return (
    <div className="ops-page">
      <header className="ops-page__header">
        <div>
          <p className="ops-eyebrow">Operations control center</p>
          <h1>{title}</h1>
          <p className="ops-muted">{description}</p>
        </div>
        <Freshness generatedAt={resource.data?.generated_at} onRefresh={resource.reload} loading={resource.loading} />
      </header>
      {resource.error && <ErrorBanner message={resource.error} onRetry={resource.reload} />}
      {resource.data ? children(resource.data) : resource.loading ? <Loading /> : null}
    </div>
  );
}
