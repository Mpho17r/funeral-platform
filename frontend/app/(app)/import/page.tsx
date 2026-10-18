"use client";

import {
  ArrowLeft,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Upload,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ErrorNote } from "@/components/Notices";
import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";

type Row = {
  line: number;
  member_number: string;
  name: string;
  plan: string;
  ok: boolean;
  errors: string[];
  warnings: string[];
};

type Report = {
  total: number;
  ready: number;
  with_errors: number;
  policies: number;
  ignored_columns: string[];
  rows: Row[];
  imported?: number;
  policies_created?: number;
  skipped?: number;
  total_amount?: string;
  imported_amount?: string;
  months_created?: number;
  policy_notes?: string[];
  memberships_updated?: number;
};

type Kind = "members" | "payments" | "cases" | "dependents" | "beneficiaries";

const WHERE: Record<Kind, { column: string; path: string; view: string }> = {
  members: { column: "Member", path: "/members", view: "View members" },
  payments: {
    column: "Payment",
    path: "/membership-payments",
    view: "View payments",
  },
  cases: { column: "Case", path: "/cases", view: "View cases" },
  dependents: {
    column: "Person",
    path: "/covered-dependents",
    view: "View dependents",
  },
  beneficiaries: {
    column: "Person",
    path: "/beneficiaries",
    view: "View beneficiaries",
  },
};

const KINDS: Record<
  Kind,
  { tab: string; title: string; intro: string; step1: string; noun: string }
> = {
  members: {
    tab: "Members",
    title: "Import members",
    intro:
      "Bring in the members and policies you already have from a spreadsheet. We check the file first and show you any problems. Nothing is saved until you confirm.",
    step1:
      "In Excel or Google Sheets, use Save as → CSV. Member number, first name and last name are required. Add a plan name and membership number to bring in the policy as well. Create the plans first under Membership Plans.",
    noun: "member",
  },
  payments: {
    tab: "Payment history",
    title: "Import payment history",
    intro:
      "Bring in the payments already taken under your old system so arrears and cover come out right. Import your members and policies first. We check the file first and nothing is saved until you confirm.",
    step1:
      "One row per payment: membership number, payment date and amount are required. Add the month the payment is for (e.g. 2026-10) so it clears that month; without it the payment is recorded but does not clear arrears. Add a receipt number as the reference so the file can be safely uploaded again.",
    noun: "payment",
  },
  cases: {
    tab: "Open cases",
    title: "Import open cases",
    intro:
      "Bring in funerals that are in progress, or recently done, so your team can carry on here without re-typing them. Cases are saved as records only. No tasks, documents or invoices are created for them. We check the file first and nothing is saved until you confirm.",
    step1:
      "One row per case: case number and the deceased's full name are required. Add the date of death (cover is judged from it), funeral date, venue, next of kin and status (open, confirmed, in progress, completed, closed or cancelled). Add a membership number to link the case to the policy.",
    noun: "case",
  },
  dependents: {
    tab: "Covered dependents",
    title: "Import covered dependents",
    intro:
      "Bring in the spouse, children and parents covered on each policy. Import your members and policies first. We check the file first and nothing is saved until you confirm.",
    step1:
      "One row per person: membership number, first name, last name and relationship are required. Words like son, daughter, wife or mother are understood. Add the date of birth and cover start date; if you leave the start date out, the policy start date is used.",
    noun: "dependent",
  },
  beneficiaries: {
    tab: "Beneficiaries",
    title: "Import beneficiaries",
    intro:
      "Bring in who is nominated to receive the payout on each policy, with their percentage share. Import your members and policies first. We check the file first and nothing is saved until you confirm.",
    step1:
      "One row per beneficiary: membership number, first name, last name, relationship and share (a percentage such as 60 or 60%) are required. The shares on one policy cannot add up to more than 100, and must total exactly 100 before a claim can be paid.",
    noun: "beneficiary",
  },
};

export default function ImportPage() {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [kind, setKind] = useState<Kind>("members");

  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get("tab");

    if (
      wanted === "payments" ||
      wanted === "cases" ||
      wanted === "members" ||
      wanted === "dependents" ||
      wanted === "beneficiaries"
    ) {
      setKind(wanted);
    }
  }, []);

  const copy = KINDS[kind];
  const base = `/imports/${kind}`;

  const done = report?.imported !== undefined;

  function switchKind(next: Kind) {
    setKind(next);
    pick(null);

    if (fileInput.current) {
      fileInput.current.value = "";
    }
  }

  function pick(next: File | null) {
    setFile(next);
    setReport(null);
    setError("");
    setShowAll(false);
  }

  async function send(path: string) {
    if (!file) {
      return;
    }

    setBusy(true);
    setError("");

    try {
      const form = new FormData();
      form.append("file", file);

      const response = await api.post<Report>(path, form);
      setReport(response.data);
    } catch (err) {
      setError(getApiErrorMessage(err, "The file could not be processed."));
    } finally {
      setBusy(false);
    }
  }

  async function downloadTemplate() {
    try {
      const response = await api.get(`${base}/template`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");

      link.href = url;
      link.download = `${kind}-template.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(
        getApiErrorMessage(err, "The template could not be downloaded."),
      );
    }
  }

  const problems = report?.rows.filter((r) => !r.ok) ?? [];
  const shown = showAll ? (report?.rows ?? []) : problems;

  return (
    <main className="min-h-screen bg-[var(--fos-page)] text-[var(--fos-text)]">
      <section className="mx-auto max-w-4xl p-6 md:p-8">
        <button
          type="button"
          onClick={() => router.push("/dashboard")}
          className="mb-4 flex items-center gap-2 text-sm font-medium text-[var(--fos-text-muted)] transition hover:text-[var(--fos-text)]"
        >
          <ArrowLeft size={16} />
          Back to Dashboard
        </button>

        <h1 className="text-2xl font-bold">{copy.title}</h1>

        <div
          role="tablist"
          aria-label="What to import"
          className="mt-4 inline-flex flex-wrap gap-1 rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-1"
        >
          {(Object.keys(KINDS) as Kind[]).map((k) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={kind === k}
              onClick={() => switchKind(k)}
              className={`rounded-lg px-4 py-1.5 text-sm font-medium transition ${
                kind === k
                  ? "bg-[var(--fos-primary)] text-white"
                  : "text-[var(--fos-text-secondary)] hover:bg-[var(--fos-surface-muted)]"
              }`}
            >
              {KINDS[k].tab}
            </button>
          ))}
        </div>

        <p className="mt-3 text-sm text-[var(--fos-text-muted)]">
          {copy.intro}
        </p>

        <ol className="mt-6 space-y-4">
          <li className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5">
            <p className="font-semibold">1. Get your list into our format</p>
            <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
              {copy.step1}
            </p>
            <button
              type="button"
              onClick={downloadTemplate}
              className="mt-3 inline-flex items-center gap-2 rounded-xl border border-[var(--fos-border)] px-4 py-2 text-sm font-medium transition hover:bg-[var(--fos-surface-muted)]"
            >
              <Download size={16} />
              Download the template
            </button>
          </li>

          <li className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5">
            <p className="font-semibold">2. Choose your file and check it</p>

            <input
              ref={fileInput}
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              onChange={(e) => pick(e.target.files?.[0] ?? null)}
            />

            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => fileInput.current?.click()}
                className="inline-flex items-center gap-2 rounded-xl border border-[var(--fos-border)] px-4 py-2 text-sm font-medium transition hover:bg-[var(--fos-surface-muted)]"
              >
                <FileSpreadsheet size={16} />
                {file ? "Choose a different file" : "Choose a CSV file"}
              </button>

              {file && (
                <span className="text-sm text-[var(--fos-text-secondary)]">
                  {file.name}
                </span>
              )}

              <button
                type="button"
                disabled={!file || busy || done}
                onClick={() => send(`${base}/check`)}
                className="ml-auto rounded-xl bg-[var(--fos-primary)] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[var(--fos-primary-hover)] disabled:opacity-50"
              >
                {busy && !report ? "Checking…" : "Check file"}
              </button>
            </div>

            {error && (
              <div className="mt-3">
                <ErrorNote message={error} />
              </div>
            )}
          </li>

          {report && (
            <li className="rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5">
              <p className="font-semibold">
                {done ? "3. Done" : "3. Review and import"}
              </p>

              {done ? (
                <p
                  role="status"
                  className="mt-3 flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700"
                >
                  <CheckCircle2 size={18} className="mt-0.5 shrink-0" />
                  <span>
                    Imported {report.imported}{" "}
                    {report.imported === 1
                      ? copy.noun
                      : copy.noun.replace(/y$/, "ie") + "s"}
                    {kind === "members" && report.policies_created
                      ? ` and ${report.policies_created} polic${report.policies_created === 1 ? "y" : "ies"}`
                      : ""}
                    {kind === "payments" && report.imported_amount
                      ? ` totalling ${report.imported_amount}, updating ${report.memberships_updated} polic${report.memberships_updated === 1 ? "y" : "ies"}`
                      : ""}
                    .
                    {report.skipped
                      ? ` ${report.skipped} row${report.skipped === 1 ? " was" : "s were"} left out because of problems (listed below). Fix them in your file and upload it again; rows already imported are skipped as duplicates.`
                      : ""}
                  </span>
                </p>
              ) : (
                <p className="mt-2 text-sm text-[var(--fos-text-secondary)]">
                  <strong>{report.ready}</strong> of {report.total} rows are
                  ready
                  {kind === "members" &&
                    report.policies > 0 &&
                    ` (including ${report.policies} polic${report.policies === 1 ? "y" : "ies"})`}
                  {kind === "payments" &&
                    report.total_amount &&
                    ` (${report.total_amount} in total)`}
                  .{" "}
                  {report.with_errors > 0 ? (
                    <>
                      <strong>{report.with_errors}</strong> have problems and
                      will be left out.
                    </>
                  ) : (
                    "No problems found."
                  )}
                </p>
              )}

              {report.ignored_columns.length > 0 && (
                <p className="mt-2 text-sm text-[var(--fos-text-muted)]">
                  Ignored columns we do not use:{" "}
                  {report.ignored_columns.join(", ")}.
                </p>
              )}

              {report.policy_notes && report.policy_notes.length > 0 && (
                <ul className="mt-3 space-y-1 text-sm text-amber-700">
                  {report.policy_notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              )}

              {shown.length > 0 && (
                <div className="mt-4 overflow-x-auto rounded-xl border border-[var(--fos-border)]">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-[var(--fos-surface-muted)] text-xs uppercase text-[var(--fos-text-muted)]">
                      <tr>
                        <th className="px-3 py-2">Row</th>
                        <th className="px-3 py-2">{WHERE[kind].column}</th>
                        <th className="px-3 py-2">What to fix</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shown.map((row) => (
                        <tr
                          key={row.line}
                          className="border-t border-[var(--fos-border)] align-top"
                        >
                          <td className="px-3 py-2">{row.line}</td>
                          <td className="px-3 py-2">
                            <div className="font-medium">
                              {row.member_number || "—"}
                            </div>
                            <div className="text-xs text-[var(--fos-text-muted)]">
                              {row.name}
                              {kind === "payments" && row.plan
                                ? ` · for ${row.plan}`
                                : ""}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            {row.errors.length === 0 &&
                            row.warnings.length === 0
                              ? "Ready"
                              : null}
                            {row.errors.map((e) => (
                              <p key={e} className="text-red-700">
                                {e}
                              </p>
                            ))}
                            {row.warnings.map((w) => (
                              <p key={w} className="text-amber-700">
                                {w}
                              </p>
                            ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {!done && report.ready > 0 && report.with_errors > 0 && (
                <button
                  type="button"
                  onClick={() => setShowAll((v) => !v)}
                  className="mt-3 text-sm font-medium underline"
                >
                  {showAll ? "Show problems only" : "Show every row"}
                </button>
              )}

              {!done && (
                <div className="mt-5 flex flex-wrap gap-3">
                  <button
                    type="button"
                    disabled={busy || report.ready === 0}
                    onClick={() => send(base)}
                    className="inline-flex items-center gap-2 rounded-xl bg-[var(--fos-primary)] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[var(--fos-primary-hover)] disabled:opacity-50"
                  >
                    <Upload size={16} />
                    {busy
                      ? "Importing…"
                      : `Import ${report.ready} row${report.ready === 1 ? "" : "s"}`}
                  </button>

                  <button
                    type="button"
                    onClick={() => pick(null)}
                    className="rounded-xl border border-[var(--fos-border)] px-4 py-2 text-sm font-medium transition hover:bg-[var(--fos-surface-muted)]"
                  >
                    Start again
                  </button>
                </div>
              )}

              {done && (
                <button
                  type="button"
                  onClick={() => router.push(WHERE[kind].path)}
                  className="mt-4 rounded-xl bg-[var(--fos-primary)] px-4 py-2 text-sm font-semibold text-white"
                >
                  {WHERE[kind].view}
                </button>
              )}
            </li>
          )}
        </ol>
      </section>
    </main>
  );
}
