import type { Metadata } from "next";
import "@breero/portal/styles.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://partners.breero.com"),
  title: "BREERO Partner",
  description: "Secure BREERO provider workspace",
  alternates: { canonical: "/" },
  robots: { index: false, follow: false },
};

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-horizon-root data-horizon-theme="breero" data-horizon-appearance="dark">
      <body>{children}</body>
    </html>
  );
}
