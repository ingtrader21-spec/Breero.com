"use client";

import { PortalLoginPage } from "@breero/portal";

import { portalRuntime } from "../../portal.config";

export default function LoginPage() {
  return <PortalLoginPage config={portalRuntime} />;
}
