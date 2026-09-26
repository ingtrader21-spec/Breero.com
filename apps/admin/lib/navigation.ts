export interface NavItem { href: string; label: string; group: string }

export const NAVIGATION: NavItem[] = [
  { href: "/", label: "Overview", group: "Workspace" },
  { href: "/users", label: "Users & access", group: "Administration" },
  { href: "/providers", label: "Provider applications", group: "Administration" },
  { href: "/geography", label: "Service zones", group: "Geography" },
  { href: "/geography/postal-codes", label: "Postal codes", group: "Geography" },
  { href: "/finance", label: "Finance overview", group: "Finance" },
  { href: "/finance/payouts", label: "Payout batches", group: "Finance" },
  { href: "/finance/payments", label: "Payments & refunds", group: "Finance" },
];

export function isActivePath(pathname: string, href: string, items: NavItem[] = NAVIGATION): boolean {
  if (href === "/") return pathname === "/";
  if (pathname === href) return true;
  if (!pathname.startsWith(`${href}/`)) return false;
  // A deeper navigation entry (e.g. /geography/postal-codes) owns its subtree.
  return !items.some((item) => item.href !== href && item.href.startsWith(`${href}/`) && (pathname === item.href || pathname.startsWith(`${item.href}/`)));
}
