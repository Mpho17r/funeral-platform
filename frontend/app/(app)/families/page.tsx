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
import { useEffect, useState } from "react";
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

export default function FamiliesPage() {
  const router = useRouter();

  const [families, setFamilies] = useState<FamilyGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedCase, setExpandedCase] = useState<string | null>(null);

  async function loadFamilies() {
    try {
      setLoading(true);
      setError("");

      const response = await api.get<FamilyGroup[]>("/families");

      setFamilies(response.data);
    } catch (err: any) {
      console.error("Families error:", err);

      if (err?.response?.status === 401) {
        removeToken();
        router.push("/login");
        return;
      }

      setError(
        err?.response?.data?.detail ||
          "Unable to load family information."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadFamilies();
  }, []);

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
    <main className="min-h-screen bg-slate-100">
      <div className="flex min-h-screen">

        <div className="min-w-0 flex-1">
      {/* HEADER */}
      <header className="border-b bg-white">
        <div className="mx-auto max-w-7xl px-6 py-5 md:px-8">
          <button
            type="button"
            onClick={() => router.push("/dashboard")}
            className="mb-5 flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-slate-900"
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
                <h1 className="text-2xl font-bold text-slate-900">
                  Families
                </h1>

                <p className="mt-1 text-sm text-slate-500">
                  Manage family members grouped by funeral case.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={loadFamilies}
              className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
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
            <div className="rounded-2xl border bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500">
                    Family Cases
                  </p>

                  <p className="mt-2 text-3xl font-bold text-slate-900">
                    {families.length}
                  </p>
                </div>

                <div className="rounded-xl bg-slate-100 p-3 text-slate-700">
                  <Users size={21} />
                </div>
              </div>
            </div>

            <div className="rounded-2xl border bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500">
                    Family Members
                  </p>

                  <p className="mt-2 text-3xl font-bold text-slate-900">
                    {families.reduce(
                      (sum, family) =>
                        sum + family.member_count,
                      0
                    )}
                  </p>
                </div>

                <div className="rounded-xl bg-slate-100 p-3 text-slate-700">
                  <Users size={21} />
                </div>
              </div>
            </div>

            <div className="rounded-2xl border bg-white p-6 shadow-sm">
              <div>
                <p className="text-sm font-medium text-slate-500">
                  Average Members per Case
                </p>

                <p className="mt-2 text-3xl font-bold text-slate-900">
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
          <div className="rounded-2xl border bg-white px-6 py-16 text-center shadow-sm">
            <RefreshCw
              size={24}
              className="mx-auto animate-spin text-slate-500"
            />

            <p className="mt-4 text-sm text-slate-500">
              Loading families...
            </p>
          </div>
        )}

        {/* EMPTY */}
        {!loading && !error && families.length === 0 && (
          <div className="rounded-2xl border bg-white px-6 py-16 text-center shadow-sm">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-500">
              <Users size={25} />
            </div>

            <h2 className="mt-5 text-base font-semibold text-slate-900">
              No families found
            </h2>

            <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
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
                  className="overflow-hidden rounded-2xl border bg-white shadow-sm"
                >
                  {/* CASE HEADER */}
                  <button
                    type="button"
                    onClick={() =>
                      toggleFamily(family.case_id)
                    }
                    className="flex w-full items-center justify-between p-6 text-left transition hover:bg-slate-50"
                  >
                    <div className="flex min-w-0 items-center gap-4">
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-700">
                        <Users size={21} />
                      </div>

                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-3">
                          <h2 className="font-bold text-slate-900">
                            {family.case_number}
                          </h2>

                          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                            {family.member_count}{" "}
                            {family.member_count === 1
                              ? "member"
                              : "members"}
                          </span>
                        </div>

                        <p className="mt-1 text-sm text-slate-500">
                          Family of{" "}
                          <span className="font-medium text-slate-700">
                            {family.deceased_full_name}
                          </span>
                        </p>
                      </div>
                    </div>

                    <div className="ml-4 shrink-0 text-slate-500">
                      {expanded ? (
                        <ChevronUp size={20} />
                      ) : (
                        <ChevronDown size={20} />
                      )}
                    </div>
                  </button>

                  {/* MEMBERS */}
                  {expanded && (
                    <div className="border-t bg-slate-50">
                      <div className="divide-y">
                        {family.members.map((member) => (
                          <div
                            key={member.id}
                            className="p-6"
                          >
                            <div className="flex flex-col justify-between gap-5 lg:flex-row">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-3">
                                  <h3 className="text-base font-bold text-slate-900">
                                    {member.full_name}
                                  </h3>

                                  <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                                    {formatRelationship(
                                      member.relationship
                                    )}
                                  </span>
                                </div>

                                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                                  {member.phone && (
                                    <div>
                                      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                                        Phone
                                      </p>

                                      <div className="mt-1 flex items-center gap-2 text-sm font-medium text-slate-700">
                                        <Phone size={15} />
                                        {member.phone}
                                      </div>
                                    </div>
                                  )}

                                  {member.email && (
                                    <div>
                                      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                                        Email
                                      </p>

                                      <div className="mt-1 flex items-center gap-2 break-all text-sm font-medium text-slate-700">
                                        <Mail size={15} />
                                        {member.email}
                                      </div>
                                    </div>
                                  )}

                                  {member.organization && (
                                    <div>
                                      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                                        Organization
                                      </p>

                                      <p className="mt-1 text-sm font-medium text-slate-700">
                                        {member.organization}
                                      </p>
                                    </div>
                                  )}
                                </div>

                                {member.address && (
                                  <div className="mt-4">
                                    <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                                      Address
                                    </p>

                                    <p className="mt-1 text-sm text-slate-600">
                                      {member.address}
                                    </p>
                                  </div>
                                )}

                                {member.notes && (
                                  <div className="mt-4 rounded-lg bg-white p-4 ring-1 ring-slate-200">
                                    <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                                      Notes
                                    </p>

                                    <p className="mt-1 text-sm text-slate-600">
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
