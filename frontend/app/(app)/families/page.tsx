"use client";

import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Mail,
  Phone,
  RefreshCw,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { removeToken } from "@/lib/auth";

type FamilyMember = {
  id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  relationship: string | null;
  organization: string | null;
  address: string | null;
  notes: string | null;
};

type FamilyGroup = {
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  member_count: number;
  members: FamilyMember[];
};

function getApiErrorDetails(error: unknown): {
  status?: number;
  detail?: string;
} {
  if (error === null || typeof error !== "object") {
    return {};
  }

  const errorRecord = error as Record<string, unknown>;
  const response = errorRecord.response;

  if (response === null || typeof response !== "object") {
    return {};
  }

  const responseRecord = response as Record<string, unknown>;
  const data = responseRecord.data;
  const detail =
    data !== null && typeof data === "object"
      ? (data as Record<string, unknown>).detail
      : undefined;

  return {
    status:
      typeof responseRecord.status === "number"
        ? responseRecord.status
        : undefined,
    detail: typeof detail === "string" ? detail : undefined,
  };
}

export default function FamiliesPage() {
  const router = useRouter();

  const [families, setFamilies] = useState<FamilyGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedCase, setExpandedCase] = useState<string | null>(null);

  const loadFamilies = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const response = await api.get<FamilyGroup[]>("/families");
      setFamilies(response.data);
    } catch (err: unknown) {
      console.error("Families error:", err);
      const { status, detail } = getApiErrorDetails(err);

      if (status === 401) {
        removeToken();
        router.push("/login");
        return;
      }

      setError(detail || "Unable to load family information.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    async function initializeFamilies() {
      await loadFamilies();
    }

    void initializeFamilies();
  }, [loadFamilies]);

  function toggleFamily(caseId: string) {
    setExpandedCase((current) =>
      current === caseId ? null : caseId
    );
  }

  function formatRelationship(value: string | null) {
    if (!value) {
      return "Family member";
    }

    return value
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) =>
        letter.toUpperCase()
      );
  }

  return (
    <main className="min-h-screen bg-[var(--fos-surface-muted)]">
      <div className="flex min-h-screen">

        <div className="min-w-0 flex-1">
      {/* HEADER */}
      <header className="border-b bg-[var(--fos-surface)]">
        <div className="mx-auto max-w-7xl px-6 py-5 md:px-8">
          <button
            type="button"
            onClick={() => router.push("/dashboard")}
            className="mb-5 flex items-center gap-2 text-sm font-medium text-[var(--fos-text-muted)] transition hover:text-[var(--fos-text)]"
          >
            <ArrowLeft size={17} />
            Back to Dashboard
          </button>

          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-slate-900 p-3 text-white">
                <Users size={22} />
              </div>

              <div>
                <h1 className="text-2xl font-bold text-[var(--fos-text)]">
                  Families
                </h1>

                <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
                  Manage family members grouped by funeral case.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={loadFamilies}
              className="flex items-center justify-center gap-2 rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-4 py-2.5 text-sm font-medium text-[var(--fos-text-secondary)] transition hover:bg-[var(--fos-page)]"
            >
              <RefreshCw size={16} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* CONTENT */}
      <section className="mx-auto max-w-7xl p-6 md:p-8">

        {/* ERROR */}
        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-medium text-red-700">
              {error}
            </p>
          </div>
        )}

        {/* SUMMARY */}
        {!loading && (
          <div className="mb-8 grid gap-5 md:grid-cols-3">
            <div className="rounded-2xl border bg-[var(--fos-surface)] p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-[var(--fos-text-muted)]">
                    Family Cases
                  </p>

                  <p className="mt-2 text-3xl font-bold text-[var(--fos-text)]">
                    {families.length}
                  </p>
                </div>

                <div className="rounded-xl bg-[var(--fos-surface-muted)] p-3 text-[var(--fos-text-secondary)]">
                  <Users size={21} />
                </div>
              </div>
            </div>

            <div className="rounded-2xl border bg-[var(--fos-surface)] p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-[var(--fos-text-muted)]">
                    Family Members
                  </p>

                  <p className="mt-2 text-3xl font-bold text-[var(--fos-text)]">
                    {families.reduce(
                      (sum, family) =>
                        sum + family.member_count,
                      0
                    )}
                  </p>
                </div>

                <div className="rounded-xl bg-[var(--fos-surface-muted)] p-3 text-[var(--fos-text-secondary)]">
                  <Users size={21} />
                </div>
              </div>
            </div>

            <div className="rounded-2xl border bg-[var(--fos-surface)] p-6 shadow-sm">
              <div>
                <p className="text-sm font-medium text-[var(--fos-text-muted)]">
                  Average Members per Case
                </p>

                <p className="mt-2 text-3xl font-bold text-[var(--fos-text)]">
                  {families.length > 0
                    ? (
                        families.reduce(
                          (sum, family) =>
                            sum + family.member_count,
                          0
                        ) / families.length
                      ).toFixed(1)
                    : "0.0"}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* LOADING */}
        {loading && (
          <div className="rounded-2xl border bg-[var(--fos-surface)] px-6 py-16 text-center shadow-sm">
            <RefreshCw
              size={24}
              className="mx-auto animate-spin text-[var(--fos-text-muted)]"
            />

            <p className="mt-4 text-sm text-[var(--fos-text-muted)]">
              Loading families...
            </p>
          </div>
        )}

        {/* EMPTY */}
        {!loading && !error && families.length === 0 && (
          <div className="rounded-2xl border bg-[var(--fos-surface)] px-6 py-16 text-center shadow-sm">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[var(--fos-surface-muted)] text-[var(--fos-text-muted)]">
              <Users size={25} />
            </div>

            <h2 className="mt-5 text-base font-semibold text-[var(--fos-text)]">
              No families found
            </h2>

            <p className="mx-auto mt-2 max-w-md text-sm text-[var(--fos-text-muted)]">
              Family members added to funeral cases will
              appear here grouped by case.
            </p>
          </div>
        )}

        {/* FAMILY GROUPS */}
        {!loading && families.length > 0 && (
          <div className="space-y-5">
            {families.map((family) => {
              const expanded =
                expandedCase === family.case_id;

              return (
                <div
                  key={family.case_id}
                  className="overflow-hidden rounded-2xl border bg-[var(--fos-surface)] shadow-sm"
                >
                  {/* CASE HEADER */}
                  <button
                    type="button"
                    onClick={() =>
                      toggleFamily(family.case_id)
                    }
                    className="flex w-full items-center justify-between p-6 text-left transition hover:bg-[var(--fos-page)]"
                  >
                    <div className="flex min-w-0 items-center gap-4">
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[var(--fos-surface-muted)] text-[var(--fos-text-secondary)]">
                        <Users size={21} />
                      </div>

                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-3">
                          <h2 className="font-bold text-[var(--fos-text)]">
                            {family.case_number}
                          </h2>

                          <span className="rounded-full bg-[var(--fos-surface-muted)] px-3 py-1 text-xs font-medium text-[var(--fos-text-secondary)]">
                            {family.member_count}{" "}
                            {family.member_count === 1
                              ? "member"
                              : "members"}
                          </span>
                        </div>

                        <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
                          Family of{" "}
                          <span className="font-medium text-[var(--fos-text-secondary)]">
                            {family.deceased_full_name}
                          </span>
                        </p>
                      </div>
                    </div>

                    <div className="ml-4 shrink-0 text-[var(--fos-text-muted)]">
                      {expanded ? (
                        <ChevronUp size={20} />
                      ) : (
                        <ChevronDown size={20} />
                      )}
                    </div>
                  </button>

                  {/* MEMBERS */}
                  {expanded && (
                    <div className="border-t bg-[var(--fos-page)]">
                      <div className="divide-y">
                        {family.members.map((member) => (
                          <div
                            key={member.id}
                            className="p-6"
                          >
                            <div className="flex flex-col justify-between gap-5 lg:flex-row">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-3">
                                  <h3 className="text-base font-bold text-[var(--fos-text)]">
                                    {member.full_name}
                                  </h3>

                                  <span className="rounded-full bg-[var(--fos-surface)] px-3 py-1 text-xs font-medium text-[var(--fos-text-secondary)] ring-1 ring-slate-200">
                                    {formatRelationship(
                                      member.relationship
                                    )}
                                  </span>
                                </div>

                                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                                  {member.phone && (
                                    <div>
                                      <p className="text-xs font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                                        Phone
                                      </p>

                                      <div className="mt-1 flex items-center gap-2 text-sm font-medium text-[var(--fos-text-secondary)]">
                                        <Phone size={15} />
                                        {member.phone}
                                      </div>
                                    </div>
                                  )}

                                  {member.email && (
                                    <div>
                                      <p className="text-xs font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                                        Email
                                      </p>

                                      <div className="mt-1 flex items-center gap-2 break-all text-sm font-medium text-[var(--fos-text-secondary)]">
                                        <Mail size={15} />
                                        {member.email}
                                      </div>
                                    </div>
                                  )}

                                  {member.organization && (
                                    <div>
                                      <p className="text-xs font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                                        Organization
                                      </p>

                                      <p className="mt-1 text-sm font-medium text-[var(--fos-text-secondary)]">
                                        {member.organization}
                                      </p>
                                    </div>
                                  )}
                                </div>

                                {member.address && (
                                  <div className="mt-4">
                                    <p className="text-xs font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                                      Address
                                    </p>

                                    <p className="mt-1 text-sm text-[var(--fos-text-secondary)]">
                                      {member.address}
                                    </p>
                                  </div>
                                )}

                                {member.notes && (
                                  <div className="mt-4 rounded-lg bg-[var(--fos-surface)] p-4 ring-1 ring-slate-200">
                                    <p className="text-xs font-medium uppercase tracking-wide text-[var(--fos-text-muted)]">
                                      Notes
                                    </p>

                                    <p className="mt-1 text-sm text-[var(--fos-text-secondary)]">
                                      {member.notes}
                                    </p>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
        </div>
      </div>
    </main>
  );
}
