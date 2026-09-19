"use client";

import { useEffect, useState } from "react";
import { customerSession } from "@/lib/customer/api";
import { keycloak } from "@/lib/keycloak";
import { routeToPortal } from "@/lib/portal";

export default function KeycloakCallback() {
  const [error, setError] = useState(false);
  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const code = query.get("code");
    const state = query.get("state");
    if (!code || !state) {
      setError(true);
      return;
    }
    keycloak
      .exchange(code, state)
      .then(async (session) => {
        customerSession.save(session);
        await routeToPortal();
      })
      .catch(() => {
        customerSession.clear();
        setError(true);
      });
  }, []);
  return error ? (
    <p role="alert">Sign-in could not be completed. Please return to the login page.</p>
  ) : (
    <p role="status">Completing secure sign-in and loading your workspace…</p>
  );
}
