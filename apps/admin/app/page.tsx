"use client";

import { PortalFoundationPage } from "@breero/portal";

import { portalRuntime } from "../portal.config";

export default function PortalHomePage() {
  return <PortalFoundationPage config={portalRuntime} />;
}
