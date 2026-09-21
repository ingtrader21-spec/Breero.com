"use client";

import { usePathname } from "next/navigation";
import { CalendarIcon, ChevronDownIcon, HomeIcon, UserIcon } from "@breero/ui";
import { customerApi, customerSession } from "@/lib/customer/api";
import { keycloak } from "@/lib/keycloak";

const links = [
  { href: "/account", label: "Overview", icon: <HomeIcon /> },
  { href: "/account/bookings", label: "Bookings", icon: <CalendarIcon /> },
  { href: "/account/quotes", label: "Quotes", icon: <QuoteIcon /> },
  { href: "/account/profile", label: "Profile & settings", icon: <UserIcon /> },
  { href: "/account/addresses", label: "Addresses", icon: <HomeIcon /> },
];

export function AccountNav() {
  const pathname = usePathname();
  const logout = async () => {
    if (keycloak.enabled) {
      await keycloak.logout();
      return;
    }
    try {
      await customerApi.auth.logout({ refresh_token: "cookie-session-not-readable-by-javascript" });
    } finally {
      customerSession.clear();
      window.location.assign("/account/login");
    }
  };
  return (
    <>
      <aside className="account-nav">
        <p>My account</p>
        <nav aria-label="Account navigation">
          {links.map((link) => {
            const active =
              link.href === "/account"
                ? pathname === link.href
                : pathname.startsWith(link.href);
            return (
              <a
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
              >
                {link.icon}
                <span>{link.label}</span>
              </a>
            );
          })}
          <button type="button" onClick={logout}>
            Log out
          </button>
        </nav>
        <div className="account-nav__help">
          <strong>Need a hand?</strong>
          <span>Our support team is here every day.</span>
          <a href="mailto:support@breero.com">Get support</a>
        </div>
      </aside>
      <div className="account-mobile-nav">
        <label htmlFor="account-section">Account section</label>
        <span>
          <select
            id="account-section"
            value={
              links.find((link) =>
                link.href === "/account"
                  ? pathname === link.href
                  : pathname.startsWith(link.href),
              )?.href ?? "/account"
            }
            onChange={(event) => window.location.assign(event.target.value)}
          >
            {links.map((link) => (
              <option key={link.href} value={link.href}>
                {link.label}
              </option>
            ))}
            <option value="/account/login">Sign in page</option>
          </select>
          <ChevronDownIcon />
        </span>
      </div>
    </>
  );
}

function QuoteIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      aria-hidden="true"
    >
      <path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z" />
      <path d="M9 8h6M9 12h6" />
    </svg>
  );
}
