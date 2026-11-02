import type { Metadata, Viewport } from "next";

import "@fontsource-variable/inter";
import "./globals.css";

import { ThemeProvider } from "@/components/ThemeProvider";
import { BrandingProvider } from "@/components/BrandingProvider";

export const metadata: Metadata = {
  title: { default: "LINDA | One Platform. Every Business.", template: "%s | LINDA" },
  description:
    "LINDA brings your entire business together in one intelligent workspace. Powered by Saccharum Technologies.",
  applicationName: "LINDA",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#101D2B",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen flex flex-col">
        <ThemeProvider>
          <BrandingProvider>
            {children}
          </BrandingProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
