import type { Metadata, Viewport } from "next";

import "@fontsource-variable/inter";
import "./globals.css";

import { ThemeProvider } from "@/components/ThemeProvider";
import { BrandingProvider } from "@/components/BrandingProvider";

export const metadata: Metadata = {
  title: {
    default: "LINDA | One Platform. Every Business.",
    template: "%s | LINDA",
  },
  description:
    "LINDA is a multi-industry business management platform. Powered by Saccharum Technologies.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
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
