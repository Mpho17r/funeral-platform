import Link from "next/link";
import type { ReactNode } from "react";

import { LindaLockup } from "@/components/LindaLogo";
import { PLATFORM_OWNER, PLATFORM_SLOGAN } from "@/lib/platform";

export const authInputClass =
  "h-12 w-full rounded-lg border border-slate-300 bg-white px-4 text-base text-slate-900 transition dark:border-slate-700 dark:bg-slate-900 dark:text-white";

export const authButtonClass =
  "flex h-12 w-full items-center justify-center gap-2 rounded-lg text-base font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60";

/** The frame shared by the pages people reach before they are signed in. */
export function AuthCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-[#f5f6f8] px-4 py-10 dark:bg-slate-950">
      <div className="flex flex-1 items-center justify-center">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="mb-8 text-[var(--linda-navy)] dark:text-white">
            <LindaLockup markSize={36} />
          </div>

          <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">
            {title}
          </h1>

          {subtitle && (
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              {subtitle}
            </p>
          )}

          <div className="mt-6">{children}</div>

          <p className="mt-8 text-center text-sm">
            <Link
              href="/login"
              className="font-medium text-slate-600 underline-offset-4 hover:text-slate-900 hover:underline dark:text-slate-400 dark:hover:text-white"
            >
              Back to sign in
            </Link>
          </p>
        </div>
      </div>

      <p className="mt-6 text-center text-xs text-slate-500 dark:text-slate-500">
        LINDA | {PLATFORM_SLOGAN} Powered by {PLATFORM_OWNER}.
      </p>
    </div>
  );
}

export function Notice({
  kind,
  children,
}: {
  kind: "error" | "success";
  children: ReactNode;
}) {
  const style =
    kind === "error"
      ? "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300"
      : "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-300";

  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={`rounded-lg border px-4 py-3 text-sm ${style}`}
    >
      {children}
    </div>
  );
}
