"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button, Checkbox, FormField, Input } from "@breero/ui";
import { customerApi, customerSession } from "@/lib/customer/api";
import { keycloak } from "@/lib/keycloak";
import { routeToPortal } from "@/lib/portal";

type Mode = "login" | "register" | "forgot" | "reset" | "verify";
export function AuthForm({ mode }: { mode: Mode }) {
  const query = useSearchParams();
  const [state, setState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  async function submit(data: FormData) {
    setState("loading"); setMessage("");
    try {
      if (mode === "login") {
        if (keycloak.enabled) { await keycloak.login(); return; }
        const session = await customerApi.auth.login({ email: String(data.get("email")), password: String(data.get("password")) });
        customerSession.save(session); await routeToPortal(); return;
      } else if (mode === "register") {
        if (keycloak.enabled) throw new Error("Account creation is not open for this release");
        const session = await customerApi.auth.register({ full_name: `${data.get("first_name")} ${data.get("last_name")}`.trim(), email: String(data.get("email")), password: String(data.get("password")) });
        customerSession.save(session); await routeToPortal(); return;
      } else if (mode === "forgot") {
        if (keycloak.enabled) throw new Error("Password recovery is managed by the secure sign-in provider");
        await customerApi.auth.forgotPassword({ email: String(data.get("email")) });
      } else if (mode === "reset") {
        if (keycloak.enabled) throw new Error("Password recovery is managed by the secure sign-in provider");
        const password = String(data.get("password"));
        if (password !== String(data.get("confirm_password"))) throw new Error("Passwords do not match");
        await customerApi.auth.resetPassword({ token: query.get("token") ?? "", new_password: password });
      } else {
        if (keycloak.enabled) throw new Error("Email verification is managed by the secure sign-in provider");
        await customerApi.auth.verifyEmail({ token: query.get("token") ?? "" });
      }
      setState("success");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "We couldn’t complete that request.");
      setState("error");
    }
  }
  if (state === "success") return <div className="approval-success" role="status"><span>✓</span><h2>{mode === "forgot" ? "Check your inbox" : mode === "verify" ? "Email verified" : mode === "reset" ? "Password updated" : "Complete"}</h2><p>{mode === "forgot" ? "If an account exists for that address, we’ve sent reset instructions." : mode === "verify" ? "Your email is confirmed. You can now use your BREERO account." : mode === "reset" ? "Sign in using your new password." : "Continue to your account."}</p><a href="/login">Go to sign in →</a></div>;
  return <form action={submit} aria-busy={state === "loading"}>
    {mode === "register" && <div className="form-grid"><FormField label="First name" htmlFor="first_name" required><Input id="first_name" name="first_name" autoComplete="given-name" required /></FormField><FormField label="Last name" htmlFor="last_name" required><Input id="last_name" name="last_name" autoComplete="family-name" required /></FormField></div>}
    {mode !== "reset" && mode !== "verify" && <FormField label="Email address" htmlFor="email" required><Input id="email" name="email" type="email" autoComplete="email" required /></FormField>}
    {(["login", "register", "reset"] as Mode[]).includes(mode) && <FormField label={mode === "reset" ? "New password" : "Password"} htmlFor="password" hint={mode !== "login" ? "Use at least 10 characters." : undefined} required><Input id="password" name="password" type="password" minLength={mode === "login" ? undefined : 10} autoComplete={mode === "login" ? "current-password" : "new-password"} required /></FormField>}
    {mode === "reset" && <FormField label="Confirm new password" htmlFor="confirm_password" required><Input id="confirm_password" name="confirm_password" type="password" minLength={10} autoComplete="new-password" required /></FormField>}
    {mode === "login" && <div className="auth-options"><Checkbox label="Keep me signed in for this browser session" /><a href="/account/forgot-password">Forgot password?</a></div>}
    {mode === "register" && <Checkbox label="I agree to the Terms and Privacy Policy" required />}
    {mode === "verify" && !query.get("token") && <p className="auth-message auth-error" role="alert">This verification link is missing its token.</p>}
    {state === "error" && <p className="auth-message auth-error" role="alert">{message || "We couldn’t complete that request. Please try again."}</p>}
    <Button type="submit" fullWidth size="lg" loading={state === "loading"} disabled={(mode === "verify" || mode === "reset") && !query.get("token")}>{mode === "login" ? "Sign in" : mode === "register" ? "Create account" : mode === "forgot" ? "Send reset link" : mode === "reset" ? "Update password" : "Verify email"}</Button>
  </form>;
}
