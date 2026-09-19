"use client";

import { useEffect, useState } from "react";
import { Badge, Card } from "@breero/ui";
import type { PortalContext } from "@breero/types";
import { loadPortalContext } from "@/lib/portal";

export function PortalHome({ title, emailHref }: { title: string; emailHref: string }) {
  const [context, setContext] = useState<PortalContext | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    loadPortalContext(controller.signal).then(setContext).catch((reason) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Workspace unavailable");
    });
    return () => controller.abort();
  }, []);
  if (error) return <div className="shell market-section"><p role="alert">{error}</p></div>;
  if (!context) return <div className="shell market-section"><p role="status">Loading workspace…</p></div>;
  const canEmail = context.permissions.includes("*") || context.permissions.includes("email.message.compose");
  return <main className="marketplace-page" data-testid="portal-dashboard"><section className="shell market-section"><p className="market-eyebrow">Authorized workspace</p><h1>{title}</h1><p>Signed in as {context.user.full_name}.</p><Badge variant="brand">{context.departments.join(" · ")}</Badge></section><section className="shell market-section"><h2>Modules</h2><div className="service-list">{canEmail && <a className="service" href={emailHref} data-testid="email-workspace-link"><strong>Email provisioning & compose</strong><p>Manage tenant domains, senders, credential references, queued messages and outbox state.</p><span className="arrow">Open email workspace →</span></a>}<Card className="service"><strong>Access scope</strong><p>{context.assignments.map((item) => `${item.department}:${item.tenant_scope}`).join(" · ")}</p></Card></div></section></main>;
}
