import type { Metadata, Viewport } from "next";

import "@fontsource-variable/figtree";
import "@fontsource-variable/newsreader";
import "./globals.css";

import { ThemeProvider } from "@/components/ThemeProvider";
import { BrandingProvider } from "@/components/BrandingProvider";

export const metadata: Metadata = {
  title: "FuneralOS",
  description: "Funeral Management Platform",
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
