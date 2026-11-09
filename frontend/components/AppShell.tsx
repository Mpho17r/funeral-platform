"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Menu, X } from "lucide-react";

import Sidebar from "@/components/Sidebar";
import { useBranding } from "@/components/BrandingProvider";
import { CurrentUserProvider, useCurrentUser } from "@/components/CurrentUserProvider";
import { LindaLockup } from "@/components/LindaLogo";
import { TourProvider } from "@/components/GuidedTour";
import TaskAlert from "@/components/TaskAlert";
import { GlobalSearch } from "@/components/GlobalSearch";
import { NotificationBell } from "@/components/NotificationBell";
import { ProfileMenu } from "@/components/ProfileMenu";
import { WorkspaceBadge } from "@/components/WorkspaceBadge";
import { RouteGuard } from "@/components/RouteGuard";
import { AccessWarning } from "@/components/AccessWarning";
import { EmailVerificationBanner } from "@/components/EmailVerificationBanner";

type AppShellProps = {
  children: React.ReactNode;
};

function AppShellContent({ children }: AppShellProps) {
  const router = useRouter();
  const { user, loading, authUnavailable, refresh } = useCurrentUser();
  const { branding, watermarkObjectUrl } = useBranding();

  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user && !authUnavailable) {
      router.replace("/login");
    }
  }, [loading, user, authUnavailable, router]);

  useEffect(() => {
    function handleSessionExpired() {
      router.replace("/login");
    }

    window.addEventListener("linda-session-expired", handleSessionExpired);
    return () => {
      window.removeEventListener("linda-session-expired", handleSessionExpired);
    };
  }, [router]);

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

  if (loading || !user || authUnavailable) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#101D2B] px-6 text-white">
        <div className="flex w-full max-w-sm flex-col items-center text-center">
          <LindaLockup markSize={48} size="lg" className="text-white" />
          {authUnavailable ? (
            <>
              <p className="mt-8 text-sm text-white/75">
                We couldn&apos;t verify your session. Check your connection and try again.
              </p>
              <button
                type="button"
                onClick={() => void refresh()}
                className="mt-5 rounded-lg bg-[#D6A85F] px-5 py-2.5 text-sm font-semibold text-[#101D2B] transition hover:opacity-90"
              >
                Try again
              </button>
            </>
          ) : (
            <>
              <span
                aria-hidden="true"
                className="mt-8 h-7 w-7 animate-spin rounded-full border-2 border-white/25 border-t-[#D6A85F]"
              />
              <p className="mt-4 text-sm text-white/75">
                Securing your workspace…
              </p>
            </>
          )}
        </div>
      </main>
    );
  }

  return (
      <TourProvider>
      <TaskAlert />
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
          {/* Desktop top bar: who is signed in */}
          <div className="sticky top-0 z-[100] hidden h-16 items-center justify-between gap-4 border-b border-[var(--fos-border)] bg-[var(--fos-surface)]/95 px-6 backdrop-blur lg:flex">
            <GlobalSearch />
            <div className="flex min-w-0 shrink-0 items-center gap-4">
              <div className="flex shrink-0 items-center gap-2">
                <NotificationBell />
                <ProfileMenu />
              </div>
            </div>
          </div>

          {/* Mobile top bar */}
          <div className="sticky top-0 z-[100] flex h-14 items-center gap-3 border-b border-[var(--fos-border)] bg-[var(--fos-surface)]/95 px-4 backdrop-blur lg:hidden">
            <button
              type="button"
              aria-label="Open menu"
              onClick={() => setMenuOpen(true)}
              className="-ml-2 flex h-10 w-10 items-center justify-center rounded-lg text-[var(--fos-text-secondary)] hover:bg-[var(--fos-surface-muted)]"
            >
              <Menu size={22} />
            </button>

            <div className="min-w-0 flex-1">
              <WorkspaceBadge compact />
            </div>

            <div className="flex items-center gap-1">
              <GlobalSearch compact />
              <NotificationBell />
              <ProfileMenu />
            </div>
          </div>

          <main
            id="main"
            className="relative z-10 min-h-screen lg:min-h-screen"
          >
            <AccessWarning />
            <EmailVerificationBanner />
            <RouteGuard>{children}</RouteGuard>
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
      </TourProvider>
  );
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <CurrentUserProvider>
      <AppShellContent>{children}</AppShellContent>
    </CurrentUserProvider>
  );
}
