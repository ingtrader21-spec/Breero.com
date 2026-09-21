import type { Metadata } from "next";
import { Manrope } from "next/font/google";
import "@breero/ui/styles.css";
import "@breero/ui/marketplace.css";
import "./globals.css";
import "./marketplace.css";
import "./brand.css";
import "./enterprise-design-system.css";
import { AppShell } from "@/components/app-shell";

const manrope = Manrope({ subsets: ["latin"], variable: "--font-br-sans", display: "swap" });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL ?? "https://breero.com"),
  title: { default: "BREERO — Home services, handled", template: "%s | BREERO" },
  description: "Request trusted professionals for repairs, maintenance and everyday home services.",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "BREERO",
    title: "BREERO — Home services, without the hassle",
    description: "Request trusted professionals for repairs, maintenance and everyday home services.",
    url: "/",
    images: [{ url: "/brand/og-default.png", width: 1200, height: 630, alt: "BREERO home services" }],
  },
  twitter: { card: "summary_large_image", images: ["/brand/og-default.png"] },
  icons: { icon: [{ url: "/brand/breero-favicon.svg", type: "image/svg+xml" }, { url: "/brand/favicon.ico" }], apple: "/brand/apple-touch-icon.png" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={manrope.variable}><body><AppShell>{children}</AppShell></body></html>;
}
