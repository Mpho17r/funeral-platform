"use client";

import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";

import Sidebar from "@/components/Sidebar";
import { useBranding } from "@/components/BrandingProvider";

type AppShellProps = {
  children: React.ReactNode;
};

export default function AppShell({ children }: AppShellProps) {
  const { branding, logoObjectUrl, watermarkObjectUrl } = useBranding();

  const [menuOpen, setMenuOpen] = useState(false);

  const businessName = branding?.name || "FuneralOS";

  // Escape closes the mobile menu, and the page behind it stops scrolling.
  useEffect(() => {
    if (!menuOpen) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }

    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [menuOpen]);

  return (
    <div className="flex min-h-screen bg-[var(--fos-page)] text-[var(--fos-text)]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-[var(--fos-surface)] focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-[var(--fos-text)] focus:shadow-lg"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <div className="relative z-30 hidden lg:block">
        <div className="sticky top-0 h-screen">
          <Sidebar />
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setMenuOpen(false)}
            className="absolute inset-0 bg-slate-950/50"
          />

          <div className="fos-drawer absolute inset-y-0 left-0 max-w-[85vw] shadow-2xl">
            <Sidebar
              onNavigate={() => setMenuOpen(false)}
              onLogout={() => setMenuOpen(false)}
            />

            <button
              type="button"
              aria-label="Close menu"
              onClick={() => setMenuOpen(false)}
              className="absolute right-[-48px] top-3 flex h-10 w-10 items-center justify-center rounded-full bg-[var(--fos-surface)] text-[var(--fos-text)] shadow-md"
            >
              <X size={20} />
            </button>
          </div>
        </div>
      )}

      {/* Main application area */}
      <div className="relative min-w-0 flex-1">
        {/* Mobile top bar */}
        <div className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-[var(--fos-border)] bg-[var(--fos-surface)]/95 px-4 backdrop-blur lg:hidden">
          <button
            type="button"
            aria-label="Open menu"
            onClick={() => setMenuOpen(true)}
            className="-ml-2 flex h-10 w-10 items-center justify-center rounded-lg text-[var(--fos-text-secondary)] hover:bg-[var(--fos-surface-muted)]"
          >
            <Menu size={22} />
          </button>

          <div className="flex min-w-0 items-center gap-2">
            {logoObjectUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={logoObjectUrl}
                alt=""
                className="h-7 w-7 rounded-md bg-[var(--fos-surface)] object-contain"
              />
            )}
            <span className="truncate text-sm font-semibold">
              {businessName}
            </span>
          </div>
        </div>

        <main id="main" className="relative z-10 min-h-screen lg:min-h-screen">
          {children}
        </main>

        {/* Tenant watermark */}
        {watermarkObjectUrl && (
          <div
            aria-hidden="true"
            className="pointer-events-none fixed inset-0 z-20"
            style={{
              backgroundImage: `url("${watermarkObjectUrl}")`,
              backgroundPosition: "center",
              backgroundRepeat: "no-repeat",
              backgroundSize: "min(55vw, 650px)",
              opacity: branding?.watermark_opacity ?? 0.05,
            }}
          />
        )}
      </div>
    </div>
  );
}
