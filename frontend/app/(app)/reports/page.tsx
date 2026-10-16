"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import api from "@/lib/api";
import {
  formatMoney,
  formatStatus,
  getApiErrorMessage,
} from "@/lib/format";
import { useBranches } from "@/lib/branches";
import {
  ALL_BRANCHES,
  BranchFilter,
} from "@/components/BranchControls";
import { Banner } from "@/components/Notices";

/* ============================================================
   TYPES
============================================================ */

type StatusCount = { status: string; count: number };

type CasesReport = {
  total_cases: number;
  from_membership: number;
  walk_in: number;
  funerals_held: number;
  by_status: StatusCount[];
  by_branch: {
    branch_id: string | null;
    branch_name: string;
    cases: number;
  }[];
};

type FinancialReport = {
  billed: string;
  collected: string;
  outstanding: string;
  cases_with_balance: number;
  by_payment_method: {
    payment_method: string;
    amount: string;
    payments: number;
  }[];
  outstanding_by_age: {
    bucket: string;
    amount: string;
    cases: number;
  }[];
  by_branch: {
    branch_id: string | null;
    branch_name: string;
    billed: string;
    collected: string;
    outstanding: string;
  }[];
};

type MembershipReport = {
  total_members: number;
  members_by_status: StatusCount[];
  memberships_by_status: StatusCount[];
  contributions_collected: string;
  claims_total: number;
  claims_by_status: {
    status: string;
    count: number;
    claimed_amount: string;
    approved_amount: string;
  }[];
  by_branch: {
    branch_id: string | null;
    branch_name: string;
    members: number;
    contributions: string;
  }[];
};

type Tab = "cases" | "financial" | "membership";

type Preset = "month" | "30" | "year" | "all" | "custom";

/* ============================================================
   DATES
============================================================ */

function isoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${date.getFullYear()}-${month}-${day}`;
}

function presetRange(preset: Preset): [string, string] {
  const today = new Date();

  if (preset === "month") {
    return [
      isoDate(new Date(today.getFullYear(), today.getMonth(), 1)),
      isoDate(today),
    ];
  }

  if (preset === "30") {
    const start = new Date(today);
    start.setDate(start.getDate() - 29);

    return [isoDate(start), isoDate(today)];
  }

  if (preset === "year") {
    return [isoDate(new Date(today.getFullYear(), 0, 1)), isoDate(today)];
  }

  return ["", ""];
}

const PRESETS: { id: Preset; label: string }[] = [
  { id: "month", label: "This month" },
  { id: "30", label: "Last 30 days" },
  { id: "year", label: "This year" },
  { id: "all", label: "All time" },
];

const TABS: { id: Tab; label: string }[] = [
  { id: "cases", label: "Cases" },
  { id: "financial", label: "Financial" },
  { id: "membership", label: "Membership" },
];

/* ============================================================
   SMALL PIECES
============================================================ */

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="mt-2 text-2xl font-bold text-gray-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-gray-500">{hint}</p>}
    </div>
  );
}

function Panel({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-200 px-5 py-4">
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        {note && <p className="mt-0.5 text-xs text-gray-500">{note}</p>}
      </div>
      {children}
    </section>
  );
}

function Empty() {
  return (
    <p className="px-5 py-8 text-center text-sm text-gray-500">
      Nothing to show for this period.
    </p>
  );
}

function Table({
  columns,
  rows,
}: {
  columns: { label: string; right?: boolean }[];
  rows: React.ReactNode[][];
}) {
  if (rows.length === 0) {
    return <Empty />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
          <tr>
            {columns.map((column) => (
              <th
                key={column.label}
                className={`px-5 py-3 font-medium ${
                  column.right ? "text-right" : "text-left"
                }`}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  className={`px-5 py-3 text-gray-700 ${
                    columns[cellIndex].right
                      ? "text-right tabular-nums"
                      : ""
                  }`}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const money = (value: string) => `R ${formatMoney(value)}`;

function methodLabel(method: string): string {
  // "eft" is an acronym, so it is not title-cased like other words.
  return method === "eft" ? "EFT" : formatStatus(method);
}

/* ============================================================
   REPORT BODIES
============================================================ */

function CasesBody({ data }: { data: CasesReport }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Cases opened" value={String(data.total_cases)} />
        <Stat
          label="From a membership"
          value={String(data.from_membership)}
        />
        <Stat label="Walk-in" value={String(data.walk_in)} />
        <Stat
          label="Funerals held"
          value={String(data.funerals_held)}
          hint="By funeral date in the period"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="By status">
          <Table
            columns={[
              { label: "Status" },
              { label: "Cases", right: true },
            ]}
            rows={data.by_status.map((row) => [
              formatStatus(row.status),
              row.count,
            ])}
          />
        </Panel>

        <Panel title="By branch">
          <Table
            columns={[
              { label: "Branch" },
              { label: "Cases", right: true },
            ]}
            rows={data.by_branch.map((row) => [
              row.branch_name,
              row.cases,
            ])}
          />
        </Panel>
      </div>
    </div>
  );
}

function FinancialBody({ data }: { data: FinancialReport }) {
  const maxAge = Math.max(
    ...data.outstanding_by_age.map((row) => Number(row.amount)),
    0
  );

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Billed"
          value={money(data.billed)}
          hint="Cases opened in the period"
        />
        <Stat
          label="Collected"
          value={money(data.collected)}
          hint="Payments dated in the period"
        />
        <Stat
          label="Outstanding now"
          value={money(data.outstanding)}
          hint={`${data.cases_with_balance} ${
            data.cases_with_balance === 1 ? "case owes" : "cases owe"
          } a balance`}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title="Outstanding by age"
          note="How long ago the case was opened. Not limited to the period."
        >
          <div className="space-y-4 px-5 py-5">
            {data.outstanding_by_age.map((row) => {
              const width =
                maxAge > 0
                  ? Math.max((Number(row.amount) / maxAge) * 100, 0)
                  : 0;

              return (
                <div key={row.bucket}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="text-gray-700">
                      {row.bucket} days
                      <span className="ml-2 text-xs text-gray-500">
                        {row.cases}{" "}
                        {row.cases === 1 ? "case" : "cases"}
                      </span>
                    </span>
                    <span className="tabular-nums text-gray-900">
                      {money(row.amount)}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-100">
                    <div
                      className="h-2 rounded-full bg-gray-800"
                      style={{ width: `${width}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>

        <Panel title="Collected by payment method">
          <Table
            columns={[
              { label: "Method" },
              { label: "Payments", right: true },
              { label: "Amount", right: true },
            ]}
            rows={data.by_payment_method.map((row) => [
              methodLabel(row.payment_method),
              row.payments,
              money(row.amount),
            ])}
          />
        </Panel>
      </div>

      <Panel title="By branch">
        <Table
          columns={[
            { label: "Branch" },
            { label: "Billed", right: true },
            { label: "Collected", right: true },
            { label: "Outstanding", right: true },
          ]}
          rows={data.by_branch.map((row) => [
            row.branch_name,
            money(row.billed),
            money(row.collected),
            money(row.outstanding),
          ])}
        />
      </Panel>
    </div>
  );
}

function MembershipBody({ data }: { data: MembershipReport }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Members"
          value={String(data.total_members)}
          hint="Right now"
        />
        <Stat
          label="Contributions collected"
          value={money(data.contributions_collected)}
          hint="Payments dated in the period"
        />
        <Stat
          label="Claims raised"
          value={String(data.claims_total)}
          hint="Raised in the period"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Members by status">
          <Table
            columns={[
              { label: "Status" },
              { label: "Members", right: true },
            ]}
            rows={data.members_by_status.map((row) => [
              formatStatus(row.status),
              row.count,
            ])}
          />
        </Panel>

        <Panel title="Memberships by status">
          <Table
            columns={[
              { label: "Status" },
              { label: "Memberships", right: true },
            ]}
            rows={data.memberships_by_status.map((row) => [
              formatStatus(row.status),
              row.count,
            ])}
          />
        </Panel>
      </div>

      <Panel title="Claims by status">
        <Table
          columns={[
            { label: "Status" },
            { label: "Claims", right: true },
            { label: "Claimed", right: true },
            { label: "Approved", right: true },
          ]}
          rows={data.claims_by_status.map((row) => [
            formatStatus(row.status),
            row.count,
            money(row.claimed_amount),
            money(row.approved_amount),
          ])}
        />
      </Panel>

      <Panel title="By branch">
        <Table
          columns={[
            { label: "Branch" },
            { label: "Members", right: true },
            { label: "Contributions", right: true },
          ]}
          rows={data.by_branch.map((row) => [
            row.branch_name,
            row.members,
            money(row.contributions),
          ])}
        />
      </Panel>
    </div>
  );
}

/* ============================================================
   PAGE
============================================================ */

export default function ReportsPage() {
  const branchData = useBranches();

  const [tab, setTab] = useState<Tab>("cases");
  const [preset, setPreset] = useState<Preset>("month");
  const [range, setRange] = useState<[string, string]>(() =>
    presetRange("month")
  );
  const [branch, setBranch] = useState(ALL_BRANCHES);

  const [report, setReport] = useState<{
    key: string;
    data: unknown;
  } | null>(null);
  const [error, setError] = useState("");

  const [from, to] = range;
  const invalidRange = Boolean(from && to && from > to);

  const key = useMemo(
    () => `${tab}|${from}|${to}|${branch}`,
    [tab, from, to, branch]
  );

  useEffect(() => {
    if (invalidRange) {
      return;
    }

    let cancelled = false;

    const params: Record<string, string> = {};

    if (from) params.date_from = from;
    if (to) params.date_to = to;
    if (branch !== ALL_BRANCHES) params.branch_id = branch;

    api
      .get(`/reports/${tab}`, { params })
      .then((response) => {
        if (!cancelled) {
          setError("");
          setReport({ key, data: response.data });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            getApiErrorMessage(err, "Could not load this report.")
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [tab, from, to, branch, key, invalidRange]);

  // Only show a report that matches what is selected, so a slow
  // response never shows figures for an earlier filter.
  const loading = !invalidRange && report?.key !== key && !error;
  const current = report?.key === key ? report.data : null;

  function choosePreset(next: Preset) {
    setPreset(next);

    if (next !== "custom") {
      setRange(presetRange(next));
    }
  }

  return (
    <div className="space-y-6 p-6 md:p-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
        <p className="mt-1 text-sm text-gray-500">
          Figures worked out from your live records. Cancelled and
          archived cases are left out of the money.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div
          role="tablist"
          className="inline-flex rounded-lg border border-gray-300 bg-white p-1"
        >
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              onClick={() => setTab(item.id)}
              className={`rounded-md px-4 py-1.5 text-sm font-medium transition ${
                tab === item.id
                  ? "bg-gray-900 text-white"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="inline-flex flex-wrap rounded-lg border border-gray-300 bg-white p-1">
          {PRESETS.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={preset === item.id}
              onClick={() => choosePreset(item.id)}
              className={`rounded-md px-3 py-1.5 text-sm transition ${
                preset === item.id
                  ? "bg-gray-100 font-semibold text-gray-900"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        <label className="text-xs text-gray-500">
          From
          <input
            type="date"
            value={from}
            max={to || undefined}
            onChange={(event) => {
              setPreset("custom");
              setRange([event.target.value, to]);
            }}
            className="mt-1 block rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-gray-900"
          />
        </label>

        <label className="text-xs text-gray-500">
          To
          <input
            type="date"
            value={to}
            min={from || undefined}
            onChange={(event) => {
              setPreset("custom");
              setRange([from, event.target.value]);
            }}
            className="mt-1 block rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-gray-900"
          />
        </label>

        {branchData.multiple && (
          <BranchFilter
            branches={branchData.branches}
            value={branch}
            onChange={setBranch}
          />
        )}
      </div>

      {invalidRange && (
        <Banner tone="error" onDismiss={() => choosePreset("month")}>
          The start date is after the end date.
        </Banner>
      )}

      {error && (
        <Banner tone="error" onDismiss={() => setError("")}>
          {error}
        </Banner>
      )}

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-gray-500">
          <Loader2 size={18} className="animate-spin" />
          Loading report…
        </div>
      ) : current ? (
        <>
          {tab === "cases" && (
            <CasesBody data={current as CasesReport} />
          )}
          {tab === "financial" && (
            <FinancialBody data={current as FinancialReport} />
          )}
          {tab === "membership" && (
            <MembershipBody data={current as MembershipReport} />
          )}
        </>
      ) : null}
    </div>
  );
}
