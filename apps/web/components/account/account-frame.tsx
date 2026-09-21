"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AccountNav } from "./account-nav";

const authRoutes = new Set([
  "/account/login",
  "/account/register",
  "/account/forgot-password",
  "/account/reset-password",
  "/account/verify",
  "/account/callback",
  "/account/session-expired",
]);

export function AccountFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (authRoutes.has(pathname)) return <div className="account-auth-page">{children}</div>;
  return <div className="account-shell"><div className="account-shell__inner"><AccountNav/><div className="account-content">{children}</div></div></div>;
}
