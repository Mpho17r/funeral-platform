
"use client";

import Sidebar from "@/components/Sidebar";
import { useBranding } from "@/components/BrandingProvider";

type AppShellProps = {
  children: React.ReactNode;
};

export default function AppShell({ children }: AppShellProps) {
  const { branding, watermarkObjectUrl } = useBranding();

  return (
    <div className="flex min-h-screen bg-slate-100 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      {/* Sidebar */}
      <div className="relative z-30">
        <Sidebar />
      </div>

      {/* Main application area */}
      <div className="relative min-w-0 flex-1">
        <main className="relative z-10 min-h-screen">
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

