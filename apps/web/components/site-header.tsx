"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRightIcon, CloseIcon, IconButton, MenuIcon, ShieldIcon, UserIcon } from "@breero/ui";
import { Logo } from "./brand/Logo";
import { navigation } from "@/content/navigation";
import { breeroDomains } from "@/content/domains";
import {
  CUSTOMER_SESSION_EVENT,
  hasCustomerSession,
  logoutCustomerSession,
} from "@/lib/customer/session-actions";

const links = navigation;

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    let cancelled = false;
    const syncSession = async () => {
      const active = await hasCustomerSession();
      if (!cancelled) setAuthenticated(active);
    };
    const onSessionChanged = () => { void syncSession(); };

    void syncSession();
    window.addEventListener("focus", onSessionChanged);
    window.addEventListener("pageshow", onSessionChanged);
    window.addEventListener("storage", onSessionChanged);
    window.addEventListener(CUSTOMER_SESSION_EVENT, onSessionChanged);
    return () => {
      cancelled = true;
      window.removeEventListener("focus", onSessionChanged);
      window.removeEventListener("pageshow", onSessionChanged);
      window.removeEventListener("storage", onSessionChanged);
      window.removeEventListener(CUSTOMER_SESSION_EVENT, onSessionChanged);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [open]);

  const logout = async () => {
    setOpen(false);
    setSigningOut(true);
    await logoutCustomerSession("/");
  };

  const accountControls = authenticated ? (
    <>
      <Link className="header-signin hz-button hz-button--secondary hz-button--small" href="/account">
        <UserIcon size={18} />
        Account
      </Link>
      <button
        className="header-signin hz-button hz-button--primary hz-button--small"
        type="button"
        disabled={signingOut}
        onClick={() => void logout()}
      >
        {signingOut ? "Signing out…" : "Log out"}
      </button>
    </>
  ) : (
    <Link className="header-signin hz-button hz-button--secondary hz-button--small" href="/account/login">
      <UserIcon size={18} />
      Sign in
    </Link>
  );

  return (
    <header className="site-header hz-site-header">
      <div className="site-header__bar hz-container hz-site-header__inner">
        <div className="hz-brand">
          <Logo light priority />
          <span className="hz-brand__domain">breero.com</span>
        </div>

        <nav className="desktop-nav hz-site-nav hz-site-nav--desktop" aria-label="Main navigation">
          {links.map((link) => (
            <Link
              className="hz-site-nav__link"
              key={link.href}
              href={link.href}
              aria-current={pathname === link.href ? "page" : undefined}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="site-header__actions hz-header-actions">
          {accountControls}
          <Link
            className="br-button br-button--primary br-button--sm header-book hz-button hz-button--primary hz-button--small"
            href="/request-service"
            data-cta="header-request-service"
          >
            Request service <ArrowRightIcon size={17} />
          </Link>
          <IconButton
            className="mobile-menu-button hz-menu-button"
            label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            aria-controls="mobile-navigation"
            onClick={() => setOpen(!open)}
          >
            {open ? <CloseIcon /> : <MenuIcon />}
          </IconButton>
        </div>
      </div>

      {open && (
        <div id="mobile-navigation" className="mobile-nav hz-mobile-panel" data-open="true">
          <div className="hz-container hz-mobile-panel__inner">
            <nav aria-label="Mobile navigation">
              {links.map((link) => (
                <Link
                  className="hz-site-nav__link"
                  key={link.href}
                  href={link.href}
                  aria-current={pathname === link.href ? "page" : undefined}
                  onClick={() => setOpen(false)}
                >
                  {link.label}<ArrowRightIcon size={18} />
                </Link>
              ))}
              {authenticated ? (
                <>
                  <Link className="hz-site-nav__link" href="/account" onClick={() => setOpen(false)}>
                    <UserIcon size={19} />Account
                  </Link>
                  <button
                    className="hz-site-nav__link"
                    type="button"
                    disabled={signingOut}
                    onClick={() => void logout()}
                  >
                    {signingOut ? "Signing out…" : "Log out"}
                  </button>
                </>
              ) : (
                <Link className="hz-site-nav__link" href="/account/login" onClick={() => setOpen(false)}>
                  <UserIcon size={19} />Sign in
                </Link>
              )}
              <a className="hz-site-nav__link" href={breeroDomains.partners}>Partner portal</a>
            </nav>
            <Link
              className="br-button br-button--primary br-button--lg br-button--full hz-button hz-button--primary"
              href="/request-service"
              onClick={() => setOpen(false)}
              data-cta="mobile-request-service"
            >
              Request service <ArrowRightIcon />
            </Link>
            <p><ShieldIcon size={17} />Provider eligibility and availability are confirmed before assignment.</p>
          </div>
        </div>
      )}
    </header>
  );
}
