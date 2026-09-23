"use client";

import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Check,
  Loader2,
  Save,
  ShieldCheck,
} from "lucide-react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";

type Business = {
  id: string;
  name: string;
  slug: string;

  grace_period_days: number;
  cover_during_arrears: boolean;
  lapse_after_days: number;
  reinstatement_policy: "automatic" | "manual" | "not_allowed";
};

type CoverPolicy = {
  grace_period_days: number;
  cover_during_arrears: boolean;
  lapse_after_days: number;
  reinstatement_policy: "automatic" | "manual" | "not_allowed";
};

function getErrorMessage(
  error: any,
  fallback: string,
) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item: any) => {
        if (typeof item === "string") {
          return item;
        }

        if (item?.msg) {
          const location = Array.isArray(item.loc)
            ? item.loc.join(".")
            : "";

          return location
            ? `${location}: ${item.msg}`
            : item.msg;
        }

        return null;
      })
      .filter(Boolean)
      .join(" | ");
  }

  if (
    detail &&
    typeof detail === "object" &&
    typeof detail.msg === "string"
  ) {
    return detail.msg;
  }

  if (typeof error?.message === "string") {
    return error.message;
  }

  return fallback;
}

export default function MembershipRulesPage() {
  const router = useRouter();

  const [business, setBusiness] =
    useState<Business | null>(null);

  const [gracePeriodDays, setGracePeriodDays] =
    useState(30);

  const [coverDuringArrears, setCoverDuringArrears] =
    useState(true);

  const [lapseAfterDays, setLapseAfterDays] =
    useState(90);

  const [reinstatementPolicy, setReinstatementPolicy] =
    useState<
      "automatic" | "manual" | "not_allowed"
    >("automatic");

  const [loading, setLoading] =
    useState(true);

  const [saving, setSaving] =
    useState(false);

  const [message, setMessage] =
    useState("");

  const [error, setError] =
    useState("");

  async function loadBusiness() {
    try {
      setLoading(true);
      setError("");
      setMessage("");

      const meResponse =
        await api.get("/auth/me");

      const businessId =
        meResponse.data?.business_id;

      if (!businessId) {
        throw new Error(
          "Your account is not linked to a business.",
        );
      }

      const businessResponse =
        await api.get(
          `/businesses/${businessId}`,
        );

      const data: Business =
        businessResponse.data;

      setBusiness(data);

      setGracePeriodDays(
        data.grace_period_days,
      );

      setCoverDuringArrears(
        data.cover_during_arrears,
      );

      setLapseAfterDays(
        data.lapse_after_days,
      );

      setReinstatementPolicy(
        data.reinstatement_policy,
      );
    } catch (err: any) {
      setError(
        getErrorMessage(
          err,
          "Unable to load membership rules.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBusiness();
  }, []);

  async function saveRules() {
    if (!business) {
      return;
    }

    setError("");
    setMessage("");

    if (gracePeriodDays < 0) {
      setError(
        "Grace period cannot be negative.",
      );
      return;
    }

    if (lapseAfterDays < 1) {
      setError(
        "Lapse period must be at least 1 day.",
      );
      return;
    }

    if (lapseAfterDays < gracePeriodDays) {
      setError(
        "Lapse period must be greater than or equal to the grace period.",
      );
      return;
    }

    const policy: CoverPolicy = {
      grace_period_days: gracePeriodDays,
      cover_during_arrears: coverDuringArrears,
      lapse_after_days: lapseAfterDays,
      reinstatement_policy: reinstatementPolicy,
    };

    try {
      setSaving(true);

      const response =
        await api.patch<Business>(
          `/businesses/${business.id}/cover-policy`,
          policy,
        );

      const updatedBusiness =
        response.data;

      setBusiness(
        updatedBusiness,
      );

      setGracePeriodDays(
        updatedBusiness.grace_period_days,
      );

      setCoverDuringArrears(
        updatedBusiness.cover_during_arrears,
      );

      setLapseAfterDays(
        updatedBusiness.lapse_after_days,
      );

      setReinstatementPolicy(
        updatedBusiness.reinstatement_policy,
      );

      setMessage(
        "Membership rules saved successfully.",
      );
    } catch (err: any) {
      setError(
        getErrorMessage(
          err,
          "Unable to save membership rules.",
        ),
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-100 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
        <div className="flex min-h-screen items-center justify-center">
          <div className="flex items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
            <Loader2
              size={20}
              className="animate-spin"
            />
            Loading membership rules...
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-100 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex min-h-20 items-center justify-between border-b border-slate-200 bg-white px-6 py-4 dark:border-slate-800 dark:bg-slate-900">
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">
              Membership Rules
            </h2>

            <p className="text-sm text-slate-500 dark:text-slate-400">
              Configure how membership cover behaves when
              contributions fall into arrears.
            </p>
          </div>
        </header>

        <section className="flex-1 p-6 md:p-8">
          <div className="mx-auto max-w-5xl">
            <div className="mb-8">
              <button
                type="button"
                onClick={() =>
                  router.push("/settings")
                }
                className="mb-4 flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
              >
                <ArrowLeft size={16} />
                Back to Settings
              </button>

              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white dark:bg-white dark:text-slate-900">
                  <ShieldCheck size={24} />
                </div>

                <div>
                  <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                    Membership Cover Rules
                  </h1>

                  <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500 dark:text-slate-400">
                    These rules control when members remain
                    covered, enter arrears, lapse, and become
                    eligible for reinstatement.
                  </p>

                  {business && (
                    <p className="mt-2 text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">
                      {business.name}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {error && (
              <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
                {error}
              </div>
            )}

            {message && (
              <div className="mb-6 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-300">
                <Check size={18} />
                {message}
              </div>
            )}

            <div className="space-y-6">
              {/* GRACE PERIOD */}
              <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="mb-5">
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                    Grace Period
                  </h2>

                  <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
                    The number of days after a contribution
                    becomes due during which cover can continue
                    when arrears cover is disabled.
                  </p>
                </div>

                <div className="max-w-sm">
                  <label
                    htmlFor="grace-period"
                    className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300"
                  >
                    Grace period
                  </label>

                  <div className="relative">
                    <input
                      id="grace-period"
                      type="number"
                      min="0"
                      value={gracePeriodDays}
                      onChange={(event) =>
                        setGracePeriodDays(
                          Number(event.target.value),
                        )
                      }
                      className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 pr-16 text-sm outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:border-slate-500 dark:focus:ring-slate-800"
                    />

                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-slate-400">
                      days
                    </span>
                  </div>
                </div>
              </section>

              {/* COVER DURING ARREARS */}
              <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                  <div className="max-w-2xl">
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                      Cover During Arrears
                    </h2>

                    <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
                      Decide whether a member remains covered
                      while their membership has unpaid
                      contributions.
                    </p>
                  </div>

                  <button
                    type="button"
                    role="switch"
                    aria-checked={
                      coverDuringArrears
                    }
                    onClick={() =>
                      setCoverDuringArrears(
                        (value) => !value,
                      )
                    }
                    className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition ${
                      coverDuringArrears
                        ? "bg-slate-900 dark:bg-white"
                        : "bg-slate-300 dark:bg-slate-700"
                    }`}
                  >
                    <span
                      className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition ${
                        coverDuringArrears
                          ? "translate-x-6"
                          : "translate-x-1"
                      } ${
                        coverDuringArrears
                          ? "dark:bg-slate-900"
                          : ""
                      }`}
                    />
                  </button>
                </div>

                <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600 dark:bg-slate-950 dark:text-slate-400">
                  {coverDuringArrears ? (
                    <>
                      <strong className="text-slate-900 dark:text-white">
                        Cover remains active during arrears.
                      </strong>{" "}
                      The member can remain covered until the
                      membership reaches the configured lapse
                      period.
                    </>
                  ) : (
                    <>
                      <strong className="text-slate-900 dark:text-white">
                        Grace-period cover applies.
                      </strong>{" "}
                      Once a member enters arrears, cover
                      continues only for the configured grace
                      period.
                    </>
                  )}
                </div>
              </section>

              {/* LAPSE */}
              <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="mb-5">
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                    Membership Lapse
                  </h2>

                  <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
                    The membership becomes lapsed once the
                    oldest unpaid contribution has remained
                    unpaid for this many days.
                  </p>
                </div>

                <div className="max-w-sm">
                  <label
                    htmlFor="lapse-after"
                    className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300"
                  >
                    Lapse after
                  </label>

                  <div className="relative">
                    <input
                      id="lapse-after"
                      type="number"
                      min="1"
                      value={lapseAfterDays}
                      onChange={(event) =>
                        setLapseAfterDays(
                          Number(event.target.value),
                        )
                      }
                      className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 pr-16 text-sm outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:border-slate-500 dark:focus:ring-slate-800"
                    />

                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-slate-400">
                      days
                    </span>
                  </div>

                  <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
                    Must be greater than or equal to the grace
                    period.
                  </p>
                </div>
              </section>

              {/* REINSTATEMENT */}
              <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="mb-5">
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                    Reinstatement Policy
                  </h2>

                  <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
                    Decide what happens when a previously
                    lapsed membership has no remaining unpaid
                    contributions.
                  </p>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <button
                    type="button"
                    onClick={() =>
                      setReinstatementPolicy(
                        "automatic",
                      )
                    }
                    className={`rounded-xl border p-4 text-left transition ${
                      reinstatementPolicy ===
                      "automatic"
                        ? "border-slate-900 bg-slate-50 ring-2 ring-slate-200 dark:border-white dark:bg-slate-800 dark:ring-slate-700"
                        : "border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-950 dark:hover:border-slate-600"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-900 dark:text-white">
                        Automatic
                      </span>

                      {reinstatementPolicy ===
                        "automatic" && (
                        <Check size={18} />
                      )}
                    </div>

                    <p className="mt-2 text-xs leading-5 text-slate-500 dark:text-slate-400">
                      Automatically return the membership to
                      active status when arrears are cleared.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      setReinstatementPolicy(
                        "manual",
                      )
                    }
                    className={`rounded-xl border p-4 text-left transition ${
                      reinstatementPolicy ===
                      "manual"
                        ? "border-slate-900 bg-slate-50 ring-2 ring-slate-200 dark:border-white dark:bg-slate-800 dark:ring-slate-700"
                        : "border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-950 dark:hover:border-slate-600"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-900 dark:text-white">
                        Manual
                      </span>

                      {reinstatementPolicy ===
                        "manual" && (
                        <Check size={18} />
                      )}
                    </div>

                    <p className="mt-2 text-xs leading-5 text-slate-500 dark:text-slate-400">
                      A Main Admin or authorised staff member
                      must reinstate the membership.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      setReinstatementPolicy(
                        "not_allowed",
                      )
                    }
                    className={`rounded-xl border p-4 text-left transition ${
                      reinstatementPolicy ===
                      "not_allowed"
                        ? "border-slate-900 bg-slate-50 ring-2 ring-slate-200 dark:border-white dark:bg-slate-800 dark:ring-slate-700"
                        : "border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-950 dark:hover:border-slate-600"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-900 dark:text-white">
                        Not Allowed
                      </span>

                      {reinstatementPolicy ===
                        "not_allowed" && (
                        <Check size={18} />
                      )}
                    </div>

                    <p className="mt-2 text-xs leading-5 text-slate-500 dark:text-slate-400">
                      Once lapsed, the membership cannot be
                      automatically reinstated.
                    </p>
                  </button>
                </div>
              </section>

              {/* SAVE */}
              <section className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="font-semibold text-slate-900 dark:text-white">
                    Save Membership Rules
                  </h2>

                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    Changes will apply to membership status and
                    coverage decisions for this business.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={saveRules}
                  disabled={
                    saving || !business
                  }
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                >
                  {saving ? (
                    <>
                      <Loader2
                        size={18}
                        className="animate-spin"
                      />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save size={18} />
                      Save Changes
                    </>
                  )}
                </button>
              </section>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
