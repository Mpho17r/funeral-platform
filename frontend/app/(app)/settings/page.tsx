"use client";

import { ArrowLeft, Clock3, Palette, ShieldCheck, Users } from "lucide-react";
import { useRouter } from "next/navigation";

export default function SettingsPage() {
  const router = useRouter();

  return (
    <main className="min-h-screen bg-slate-100 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-20 items-center justify-between border-b border-slate-200 bg-white px-6 dark:border-slate-800 dark:bg-slate-900">
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">
              Settings
            </h2>

            <p className="text-sm text-slate-500 dark:text-slate-400">
              Manage your funeral business configuration
            </p>
          </div>
        </header>

        <section className="flex-1 p-6 md:p-8">
          <div className="mx-auto max-w-5xl">
            <div className="mb-8">
              <button
                type="button"
                onClick={() => router.push("/dashboard")}
                className="mb-4 flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
              >
                <ArrowLeft size={16} />
                Back to Dashboard
              </button>

              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                Business Settings
              </h1>

              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Configure how your funeral business operates and appears
                inside FuneralOS.
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              {/* BUSINESS BRANDING */}
              <button
                type="button"
                onClick={() => router.push("/settings/branding")}
                className="group rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
              >
                <div className="flex items-start justify-between">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                    <Palette size={22} />
                  </div>

                  <span className="text-sm text-slate-400 transition group-hover:text-slate-700 dark:text-slate-500 dark:group-hover:text-slate-200">
                    Configure →
                  </span>
                </div>

                <h3 className="mt-5 text-lg font-semibold text-slate-900 dark:text-white">
                  Business Branding
                </h3>

                <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
                  Manage your business logo, colours, watermark and
                  appearance across FuneralOS.
                </p>
              </button>

              {/* TEAM & USERS */}
              <button
                type="button"
                onClick={() => router.push("/settings/team")}
                className="group rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
              >
                <div className="flex items-start justify-between">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                    <Users size={22} />
                  </div>
                  <span className="text-sm text-slate-400 transition group-hover:text-slate-700 dark:text-slate-500 dark:group-hover:text-slate-200">
                    Manage →
                  </span>
                </div>
                <h3 className="mt-5 text-lg font-semibold text-slate-900 dark:text-white">
                  Team & Users
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
                  Manage staff accounts, roles and access to your funeral business.
                </p>
              </button>

              {/* ATTENDANCE & STAFF */}
              <button
                type="button"
                onClick={() => router.push("/settings/attendance")}
                className="group rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
              >
                <div className="flex items-start justify-between">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                    <Clock3 size={22} />
                  </div>

                  <span className="text-sm text-slate-400 transition group-hover:text-slate-700 dark:text-slate-500 dark:group-hover:text-slate-200">
                    Configure →
                  </span>
                </div>

                <h3 className="mt-5 text-lg font-semibold text-slate-900 dark:text-white">
                  Attendance & Staff
                </h3>

                <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
                  Configure workday presence, idle timeouts, staff break durations,
                  warnings and break expiry behaviour.
                </p>
              </button>

              {/* MEMBERSHIP RULES */}
              <button
                type="button"
                onClick={() =>
                  router.push("/settings/membership-rules")
                }
                className="group rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
              >
                <div className="flex items-start justify-between">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                    <ShieldCheck size={22} />
                  </div>

                  <span className="text-sm text-slate-400 transition group-hover:text-slate-700 dark:text-slate-500 dark:group-hover:text-slate-200">
                    Configure →
                  </span>
                </div>

                <h3 className="mt-5 text-lg font-semibold text-slate-900 dark:text-white">
                  Membership Rules
                </h3>

                <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
                  Configure contribution grace periods, arrears cover,
                  membership lapse rules and reinstatement policies.
                </p>
              </button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

