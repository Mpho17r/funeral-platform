"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";

import api from "@/lib/api";
import {
  formatDate,
  formatMoney,
  formatRand,
  methodLabel,
  getApiErrorMessage,
} from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, Field, inputClass } from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";
import { Panel } from "@/components/dashboards/Shared";

type MethodRow = {
  payment_method: string;
  receipts: number;
  expenses: number;
  expected: number;
  record: {
    counted_amount: number;
    expected_amount: number;
    variance: number;
    notes: string | null;
    needs_review: boolean;
  } | null;
};

type Position = {
  date: string;
  methods: MethodRow[];
  open_days: {
    date: string;
    open: number;
    needs_review: number;
    expected: number;
  }[];
};

type HistoryRow = {
  id: string;
  date: string;
  payment_method: string;
  expected_amount: number;
  counted_amount: number;
  variance: number;
  notes: string | null;
};

function today() {
  return new Date().toISOString().slice(0, 10);
}

function varianceText(value: number) {
  if (Math.abs(value) < 0.005) return "Balanced";
  return value > 0
    ? `R ${formatMoney(value)} over`
    : `R ${formatMoney(Math.abs(value))} short`;
}

export default function ReconciliationPage() {
  const { can } = useCurrentUser();
  const canManage = can("reconciliation.manage");

  const [day, setDay] = useState(today());
  const [position, setPosition] = useState<Position | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const [target, setTarget] = useState<MethodRow | null>(null);
  const [counted, setCounted] = useState("");
  const [notes, setNotes] = useState("");
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [pos, hist] = await Promise.all([
          api.get<Position>("/reconciliation", { params: { date: day } }),
          api.get<{ items: HistoryRow[] }>("/reconciliation/history", {
            params: { limit: 20 },
          }),
        ]);
        if (!cancelled) {
          setPosition(pos.data);
          setHistory(hist.data.items);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(getApiErrorMessage(err, "Could not load reconciliation."));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [day, reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  function openReconcile(row: MethodRow) {
    setTarget(row);
    setCounted(row.record ? String(row.record.counted_amount) : "");
    setNotes(row.record?.notes ?? "");
    setDialogError("");
  }

  const countedNumber = Number(counted);
  const variance =
    target && counted !== "" ? countedNumber - target.expected : 0;
  const needsNote = target && counted !== "" && Math.abs(variance) >= 0.005;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!target) return;

    setSaving(true);
    setDialogError("");

    try {
      await api.post("/reconciliation", {
        recon_date: day,
        payment_method: target.payment_method,
        counted_amount: counted,
        notes: notes.trim() || null,
      });
      setNotice(`${methodLabel(target.payment_method)} reconciled.`);
      setTarget(null);
      reload();
    } catch (err) {
      setDialogError(getApiErrorMessage(err, "Could not save this count."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6 md:p-8">
      <div>
        <h1 className="text-2xl font-bold text-[var(--fos-text)]">
          Daily reconciliation
        </h1>
        <p className="text-sm text-[var(--fos-text-muted)]">
          Count what is really there for each way of paying and compare it with
          what the books say: receipts in, minus expenses out.
        </p>
      </div>

      {notice && (
        <Banner tone="success" onDismiss={() => setNotice("")}>
          {notice}
        </Banner>
      )}
      {error && (
        <Banner tone="error" onDismiss={() => setError("")}>
          {error}
        </Banner>
      )}

      {position && position.open_days.length > 0 && (
        <Panel title="Days still to reconcile">
          <ul className="divide-y divide-[var(--fos-border)]">
            {position.open_days.map((d) => (
              <li key={d.date}>
                <button
                  type="button"
                  onClick={() => setDay(d.date)}
                  className="flex w-full items-center justify-between gap-3 px-5 py-3 text-left text-sm hover:bg-[var(--fos-surface-muted)]"
                >
                  <span className="font-medium text-[var(--fos-text)]">
                    {formatDate(d.date)}
                  </span>
                  <span className="text-[var(--fos-text-muted)]">
                    {d.open > 0 && `${d.open} to count`}
                    {d.open > 0 && d.needs_review > 0 && " · "}
                    {d.needs_review > 0 && `${d.needs_review} changed since counted`}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="flex items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-[var(--fos-text-muted)]">Day</span>
          <input
            type="date"
            max={today()}
            className={inputClass}
            value={day}
            onChange={(e) => e.target.value && setDay(e.target.value)}
          />
        </label>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 text-sm text-[var(--fos-text-muted)]">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </p>
      ) : position && position.methods.length === 0 ? (
        <p className="rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 text-sm text-[var(--fos-text-muted)]">
          No money moved on {formatDate(day)}.
        </p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {position?.methods.map((row) => {
            const rec = row.record;
            return (
              <section
                key={row.payment_method}
                className="rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-5 shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-[var(--fos-text)]">
                    {methodLabel(row.payment_method)}
                  </h2>
                  {rec && !rec.needs_review && (
                    <span className="flex items-center gap-1 text-xs font-medium text-emerald-600">
                      <CheckCircle2 size={14} /> Reconciled
                    </span>
                  )}
                  {rec?.needs_review && (
                    <span className="flex items-center gap-1 text-xs font-medium text-amber-600">
                      <AlertTriangle size={14} /> Changed since counted
                    </span>
                  )}
                </div>

                <dl className="mt-3 space-y-1 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-[var(--fos-text-muted)]">Receipts in</dt>
                    <dd className="text-[var(--fos-text)]">R {formatMoney(row.receipts)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-[var(--fos-text-muted)]">Expenses out</dt>
                    <dd className="text-[var(--fos-text)]">− R {formatMoney(row.expenses)}</dd>
                  </div>
                  <div className="flex justify-between border-t border-[var(--fos-border)] pt-1 font-semibold">
                    <dt className="text-[var(--fos-text)]">Should be there</dt>
                    <dd className="text-[var(--fos-text)]">{formatRand(row.expected)}</dd>
                  </div>
                  {rec && (
                    <>
                      <div className="flex justify-between">
                        <dt className="text-[var(--fos-text-muted)]">Counted</dt>
                        <dd className="text-[var(--fos-text)]">{formatRand(rec.counted_amount)}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-[var(--fos-text-muted)]">Result</dt>
                        <dd
                          className={
                            Math.abs(rec.variance) < 0.005
                              ? "text-emerald-600"
                              : "font-medium text-red-600"
                          }
                        >
                          {varianceText(rec.variance)}
                        </dd>
                      </div>
                      {rec.notes && (
                        <p className="pt-1 text-xs text-[var(--fos-text-muted)]">
                          Note: {rec.notes}
                        </p>
                      )}
                    </>
                  )}
                </dl>

                {canManage && (
                  <button
                    type="button"
                    onClick={() => openReconcile(row)}
                    className="mt-4 w-full rounded-lg bg-[var(--fos-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--fos-on-primary)]"
                  >
                    {rec ? (rec.needs_review ? "Count again" : "Recount") : "Enter counted amount"}
                  </button>
                )}
              </section>
            );
          })}
        </div>
      )}

      <Panel title="Recent reconciliations">
        {history.length === 0 ? (
          <p className="p-5 text-sm text-[var(--fos-text-muted)]">
            Nothing reconciled yet.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="border-b border-[var(--fos-border)] text-[var(--fos-text-muted)]">
                <tr>
                  <th className="p-3 font-medium">Day</th>
                  <th className="p-3 font-medium">Method</th>
                  <th className="p-3 text-right font-medium">Expected</th>
                  <th className="p-3 text-right font-medium">Counted</th>
                  <th className="p-3 font-medium">Result</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id} className="border-b border-[var(--fos-border)] last:border-0">
                    <td className="p-3 text-[var(--fos-text)]">{formatDate(h.date)}</td>
                    <td className="p-3 text-[var(--fos-text)]">{methodLabel(h.payment_method)}</td>
                    <td className="p-3 text-right text-[var(--fos-text)]">{formatRand(h.expected_amount)}</td>
                    <td className="p-3 text-right text-[var(--fos-text)]">{formatRand(h.counted_amount)}</td>
                    <td className={`p-3 ${Math.abs(h.variance) < 0.005 ? "text-emerald-600" : "font-medium text-red-600"}`}>
                      {varianceText(h.variance)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {target && (
        <Dialog
          title={`Reconcile ${methodLabel(target.payment_method)} · ${formatDate(day)}`}
          onClose={() => setTarget(null)}
        >
          <form onSubmit={submit} className="space-y-4">
            <p className="text-sm text-slate-600">
              The books say there should be{" "}
              <strong>{formatRand(target.expected)}</strong>.
            </p>
            <Field label="Amount counted or banked (R)">
              <input
                required
                autoFocus
                type="number"
                min="0"
                step="0.01"
                className={inputClass}
                value={counted}
                onChange={(e) => setCounted(e.target.value)}
              />
            </Field>
            {counted !== "" && (
              <p
                className={`text-sm font-medium ${
                  needsNote ? "text-red-600" : "text-emerald-600"
                }`}
              >
                {varianceText(variance)}
              </p>
            )}
            <Field
              label={needsNote ? "Why is it different? (required)" : "Notes (optional)"}
            >
              <textarea
                rows={2}
                className={inputClass}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </Field>
            {dialogError && <ErrorNote message={dialogError} />}
            <DialogFooter
              onClose={() => setTarget(null)}
              saving={saving}
              submitLabel="Save count"
              disabled={counted === "" || (!!needsNote && notes.trim().length < 3)}
            />
          </form>
        </Dialog>
      )}
    </div>
  );
}
