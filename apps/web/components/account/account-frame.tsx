"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  CUSTOMER_SESSION_EVENT,
  hasCustomerSession,
} from "@/lib/customer/session-actions";
import { AccountNav } from "./account-nav";

const publicAccountRoutes = new Set([
  "/account/login",
  "/account/register",
  "/account/forgot-password",
  "/account/reset-password",
  "/account/verify",
  "/account/callback",
  "/account/session-expired",
  "/account/forbidden",
]);

export function AccountFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isPublicRoute = publicAccountRoutes.has(pathname);
  const [authorized, setAuthorized] = useState(isPublicRoute);

  useEffect(() => {
    let cancelled = false;
    if (isPublicRoute) {
      setAuthorized(true);
      return () => { cancelled = true; };
    }

    const syncSession = async () => {
      const active = await hasCustomerSession();
      if (cancelled) return;
      if (active) {
        setAuthorized(true);
        return;
      }
      setAuthorized(false);
      router.replace(`/account/login?next=${encodeURIComponent(pathname)}`);
    };

    void syncSession();
    const onSessionChanged = () => { void syncSession(); };
    window.addEventListener(CUSTOMER_SESSION_EVENT, onSessionChanged);
    return () => {
      cancelled = true;
      window.removeEventListener(CUSTOMER_SESSION_EVENT, onSessionChanged);
    };
  }, [isPublicRoute, pathname, router]);

  if (isPublicRoute) {
    return <div className="account-auth-page">{children}</div>;
  }

  if (!authorized) {
    return (
      <div className="account-auth-page">
        <p role="status">Checking secure session…</p>
      </div>
    );
  }

  return (
    <div className="account-shell">
      <div className="account-shell__inner">
        <AccountNav />
        <div className="account-content">{children}</div>
      </div>
    </div>
  );
}
