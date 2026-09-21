"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Badge, Button, Card, Checkbox, FormField, Input, Select, Textarea } from "@breero/ui";
import type { EmailCredential, EmailDomain, EmailOutboxEntry, EmailSender, PortalContext } from "@breero/types";
import { customerApi } from "@/lib/customer/api";
import { loadPortalContext } from "@/lib/portal";

type ResourceState = {
  domains: EmailDomain[];
  senders: EmailSender[];
  credentials: EmailCredential[];
  outbox: EmailOutboxEntry[];
};

const emptyResources: ResourceState = { domains: [], senders: [], credentials: [], outbox: [] };
const hasPermission = (context: PortalContext, permission: string) => context.permissions.includes("*") || context.permissions.includes(permission);

export function EmailWorkspace() {
  const [context, setContext] = useState<PortalContext | null>(null);
  const [resources, setResources] = useState<ResourceState>(emptyResources);
  const [vendorId, setVendorId] = useState("");
  const [state, setState] = useState<"loading" | "idle" | "saving" | "error">("loading");
  const [message, setMessage] = useState("");

  const loadResources = useCallback(async () => {
    const [domains, senders, credentials, outbox] = await Promise.all([
      customerApi.email.domains(), customerApi.email.senders(), customerApi.email.credentials(), customerApi.email.outbox(),
    ]);
    setResources({ domains, senders, credentials, outbox });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadPortalContext(controller.signal).then(async (portal) => {
      if (!hasPermission(portal, "email.domain.read") || !hasPermission(portal, "email.message.compose")) {
        window.location.replace(portal.dashboard_path);
        return;
      }
      const vendor = portal.assignments.find((item) => item.tenant_scope === "vendor" && item.vendor_id)?.vendor_id ?? "";
      setContext(portal);
      setVendorId(vendor);
      await loadResources();
      setState("idle");
    }).catch((error) => {
      if (!controller.signal.aborted) {
        setMessage(error instanceof Error ? error.message : "Email workspace could not be loaded");
        setState("error");
      }
    });
    return () => controller.abort();
  }, [loadResources]);

  const providerVendorId = context?.assignments.find((item) => item.tenant_scope === "vendor" && item.vendor_id)?.vendor_id ?? null;
  const vendorLocked = Boolean(context?.roles.includes("vendor_admin") && providerVendorId);
  const scope = useMemo(() => ({ brand_key: context?.brand_key ?? "breero", vendor_id: vendorId || null }), [context?.brand_key, vendorId]);
  const secretPrefix = scope.vendor_id ? `breero-email/vendor/${scope.vendor_id}/` : `breero-email/brand/${scope.brand_key}/`;
  const canManageDomains = Boolean(context && hasPermission(context, "email.domain.manage"));
  const canVerifyDomains = Boolean(context && hasPermission(context, "email.domain.verify"));
  const canManageSenders = Boolean(context && hasPermission(context, "email.sender.manage"));
  const canManageCredentials = Boolean(context && hasPermission(context, "email.credential.manage"));

  async function run(action: () => Promise<unknown>, success: string) {
    setState("saving"); setMessage("");
    try {
      await action();
      await loadResources();
      setMessage(success);
      setState("idle");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The request could not be completed");
      setState("error");
    }
  }

  async function createDomain(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await run(() => customerApi.email.createDomain({
      ...scope,
      domain: String(data.get("domain")),
      dkim_selector: String(data.get("dkim_selector") || "") || null,
      return_path_domain: String(data.get("return_path_domain") || "") || null,
    }), "Domain added. It must be independently verified before sending.");
    event.currentTarget.reset();
  }

  async function createSender(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await run(() => customerApi.email.createSender({
      ...scope,
      domain_id: String(data.get("domain_id")),
      local_part: String(data.get("local_part")),
      display_name: String(data.get("display_name")),
      reply_to: String(data.get("reply_to") || "") || null,
    }), "Sender created.");
    event.currentTarget.reset();
  }

  async function createCredential(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const secretRef = String(data.get("secret_ref"));
    if (!secretRef.startsWith(secretPrefix)) {
      setState("error"); setMessage(`Secret reference must start with ${secretPrefix}`); return;
    }
    await run(() => customerApi.email.createCredential({
      ...scope,
      provider: "smtp",
      label: String(data.get("label")),
      username: String(data.get("username") || "") || null,
      secret_ref: secretRef,
      smtp_host: String(data.get("smtp_host")),
      smtp_port: Number(data.get("smtp_port")),
      use_tls: data.get("use_tls") === "on",
    }), "Credential metadata saved. Secret material remains outside the application database.");
    event.currentTarget.reset();
  }

  async function compose(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await run(() => customerApi.email.compose({
      ...scope,
      sender_id: String(data.get("sender_id")),
      credential_id: String(data.get("credential_id")),
      to_email: String(data.get("to_email")),
      subject: String(data.get("subject")),
      text_body: String(data.get("text_body")),
      idempotency_key: `email-ui-${crypto.randomUUID()}`,
    }), "Message accepted by the backend and queued through the durable outbox.");
    event.currentTarget.reset();
  }

  if (state === "loading") return <div className="shell market-section"><p role="status">Loading tenant email workspace…</p></div>;
  if (!context) return <div className="shell market-section"><p role="alert">{message || "Email workspace unavailable."}</p></div>;

  const verifiedDomains = resources.domains.filter((item) => item.verification_status === "VERIFIED");
  return <main className="marketplace-page" data-testid="tenant-email-workspace">
    <section className="shell market-section">
      <p className="market-eyebrow">Tenant communications</p>
      <h1>Email provisioning & delivery</h1>
      <p>Provision a tenant domain and sender, bind a runtime credential reference, compose a message, and inspect its durable outbox state.</p>
      <Card><strong>{context.user.full_name}</strong><p>{scope.vendor_id ? `Vendor scope: ${scope.vendor_id}` : `Brand scope: ${scope.brand_key}`}</p><p>Identity: {context.identity_mode === "keycloak" ? "Secure SSO" : "Local development"}</p></Card>
      {!vendorLocked && <FormField label="Optional vendor UUID" htmlFor="email-vendor-scope" hint="Leave blank for BREERO brand scope. Use a vendor UUID to administer that tenant."><Input id="email-vendor-scope" value={vendorId} onChange={(event) => setVendorId(event.target.value.trim())}/></FormField>}
      {message && <p role={state === "error" ? "alert" : "status"}>{message}</p>}
    </section>

    <section className="shell market-section" aria-labelledby="domains-heading">
      <h2 id="domains-heading">1. Domains</h2>
      {canManageDomains && <Card><form onSubmit={createDomain} data-testid="email-domain-form"><FormField label="Sending domain" htmlFor="email-domain" required><Input id="email-domain" name="domain" placeholder="mail.example.com" required/></FormField><FormField label="DKIM selector" htmlFor="email-dkim"><Input id="email-dkim" name="dkim_selector" placeholder="breero"/></FormField><FormField label="Return-path domain" htmlFor="email-return-path"><Input id="email-return-path" name="return_path_domain" placeholder="bounce.example.com"/></FormField><Button type="submit" loading={state === "saving"}>Add domain</Button></form></Card>}
      <div className="service-list">{resources.domains.map((domain) => <Card className="service" key={domain.id}><strong>{domain.domain}</strong><p>{domain.vendor_id ? `Vendor ${domain.vendor_id}` : "BREERO brand"}</p><Badge variant={domain.verification_status === "VERIFIED" ? "success" : "warning"}>{domain.verification_status}</Badge>{canVerifyDomains && domain.verification_status !== "VERIFIED" && <Button type="button" size="sm" variant="outline" onClick={() => run(() => customerApi.email.setDomainVerification(domain.id, true), "Domain marked verified after trusted verification.")}>Mark verified</Button>}</Card>)}</div>
    </section>

    <section className="shell market-section" aria-labelledby="senders-heading">
      <h2 id="senders-heading">2. Senders</h2>
      {canManageSenders && <Card><form onSubmit={createSender} data-testid="email-sender-form"><FormField label="Verified domain" htmlFor="sender-domain" required><Select id="sender-domain" name="domain_id" required defaultValue=""><option value="" disabled>Select domain</option>{verifiedDomains.map((domain) => <option key={domain.id} value={domain.id}>{domain.domain}</option>)}</Select></FormField><FormField label="Local part" htmlFor="sender-local" required><Input id="sender-local" name="local_part" placeholder="support" required/></FormField><FormField label="Display name" htmlFor="sender-name" required><Input id="sender-name" name="display_name" placeholder="BREERO Support" required/></FormField><FormField label="Reply-to" htmlFor="sender-reply"><Input id="sender-reply" name="reply_to" type="email"/></FormField><Button type="submit" loading={state === "saving"}>Create sender</Button></form></Card>}
      <div className="service-list">{resources.senders.map((sender) => <Card className="service" key={sender.id}><strong>{sender.display_name}</strong><p>{sender.local_part}@{resources.domains.find((item) => item.id === sender.domain_id)?.domain ?? "domain"}</p></Card>)}</div>
    </section>

    <section className="shell market-section" aria-labelledby="credentials-heading">
      <h2 id="credentials-heading">3. Credential reference</h2>
      <p>The application stores only a reference. The SMTP password/API secret must be mounted separately at runtime.</p>
      {canManageCredentials && <Card><form onSubmit={createCredential} data-testid="email-credential-form"><FormField label="Credential label" htmlFor="credential-label" required><Input id="credential-label" name="label" placeholder="Primary SMTP" required/></FormField><FormField label="SMTP host" htmlFor="credential-host" required><Input id="credential-host" name="smtp_host" required/></FormField><FormField label="SMTP port" htmlFor="credential-port" required><Input id="credential-port" name="smtp_port" type="number" min="1" max="65535" defaultValue="587" required/></FormField><FormField label="Username" htmlFor="credential-user"><Input id="credential-user" name="username"/></FormField><FormField label="Secret reference" htmlFor="credential-secret-ref" required hint={`Required prefix: ${secretPrefix}`}><Input id="credential-secret-ref" name="secret_ref" defaultValue={`${secretPrefix}smtp/main`} required/></FormField><Checkbox name="use_tls" label="Use TLS" defaultChecked/><Button type="submit" loading={state === "saving"}>Save credential metadata</Button></form></Card>}
      <div className="service-list">{resources.credentials.map((credential) => <Card className="service" key={credential.id}><strong>{credential.label}</strong><p>{credential.provider} · {credential.smtp_host ?? "provider managed"}</p><Badge variant={credential.secret_configured ? "success" : "danger"}>{credential.secret_configured ? "Secret reference configured" : "Missing secret reference"}</Badge></Card>)}</div>
    </section>

    <section className="shell market-section" aria-labelledby="compose-heading">
      <h2 id="compose-heading">4. Compose</h2>
      <Card><form onSubmit={compose} data-testid="email-compose-form"><FormField label="Sender" htmlFor="compose-sender" required><Select id="compose-sender" name="sender_id" required defaultValue=""><option value="" disabled>Select sender</option>{resources.senders.map((sender) => <option key={sender.id} value={sender.id}>{sender.display_name}</option>)}</Select></FormField><FormField label="Credential" htmlFor="compose-credential" required><Select id="compose-credential" name="credential_id" required defaultValue=""><option value="" disabled>Select credential</option>{resources.credentials.map((credential) => <option key={credential.id} value={credential.id}>{credential.label}</option>)}</Select></FormField><FormField label="Recipient" htmlFor="compose-to" required><Input id="compose-to" name="to_email" type="email" required/></FormField><FormField label="Subject" htmlFor="compose-subject" required><Input id="compose-subject" name="subject" required/></FormField><FormField label="Message" htmlFor="compose-body" required><Textarea id="compose-body" name="text_body" rows={8} required/></FormField><Button type="submit" loading={state === "saving"}>Queue message</Button></form></Card>
    </section>

    <section className="shell market-section" aria-labelledby="outbox-heading">
      <div className="section-heading"><div><p className="market-eyebrow">Durable delivery</p><h2 id="outbox-heading">5. Outbox</h2></div><Button type="button" variant="outline" onClick={() => run(loadResources, "Outbox refreshed.")}>Refresh</Button></div>
      <div className="service-list" data-testid="email-outbox">{resources.outbox.map((entry) => <Card className="service" key={entry.id}><strong>{entry.status}</strong><p>Message {entry.message_id}</p><p>Attempts: {entry.attempts}</p>{entry.last_error_code && <Badge variant="danger">{entry.last_error_code}</Badge>}</Card>)}</div>
    </section>
  </main>;
}
