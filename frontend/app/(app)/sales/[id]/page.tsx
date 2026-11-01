"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  ArrowLeft,
  Ban,
  CheckCircle2,
  CreditCard,
  FileText,
  Pencil,
  Printer,
  Send,
  Trash2,
  XCircle,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";

import api from "@/lib/api";
import { formatRand, getApiErrorMessage, methodLabel } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";
import SalesDocumentForm, { type DocumentFormValues } from "@/components/SalesDocumentForm";
import { docStatusLabel, docStatusTone, printSalesDocument, type SalesDoc } from "@/lib/sales";

const METHODS = ["cash", "card", "eft", "mobile", "other"];
const today = () => new Date().toISOString().slice(0, 10);

type Dlg = null | "edit" | "pay" | "void" | { voidPayment: string };

export default function SalesDocumentPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const { can, user } = useCurrentUser();
  const [doc, setDoc] = useState<SalesDoc | null>(null);
  const [dlg, setDlg] = useState<Dlg>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await api.get<SalesDoc>(`/sales/documents/${id}`);
      setDoc(r.data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load this document."));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(path: string, body?: object) {
    try {
      setBusy(true);
      setError("");
      const r = await api.post<SalesDoc>(`/sales/documents/${id}/${path}`, body ?? {});
      if (path === "convert") router.push(`/sales/${r.data.id}`);
      else setDoc(r.data);
    } catch (err) {
      setError(getApiErrorMessage(err, "That did not work."));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("Delete this draft?")) return;
    try {
      await api.delete(`/sales/documents/${id}`);
      router.push("/sales");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not delete."));
    }
  }

  if (!doc) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        {error ? <ErrorNote message={error} /> : <p className="text-sm text-slate-500">Loading…</p>}
      </main>
    );
  }

  const manage = can("sales.manage");
  const invoice = doc.document_type === "invoice";
  const draft = doc.status === "draft";

  return (
    <main className="mx-auto max-w-3xl space-y-5 p-4 sm:p-6">
      <button
        type="button"
        onClick={() => router.push("/sales")}
        className="flex items-center gap-1 text-sm text-slate-600 hover:underline"
      >
        <ArrowLeft size={16} /> Quotes &amp; invoices
      </button>

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">
            {invoice ? "Invoice" : "Quote"} {doc.number ?? "(draft)"}
          </h1>
          <p className="text-sm text-slate-500">{doc.customer_name}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm font-medium ${docStatusTone(doc)}`}>
          {docStatusLabel(doc)}
        </span>
      </header>

      {error && <ErrorNote message={error} />}

      <section className="rounded-2xl border bg-white p-5">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="py-2">Description</th>
              <th className="py-2 text-right">Qty</th>
              <th className="py-2 text-right">Price</th>
              <th className="py-2 text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {(doc.lines ?? []).map((l) => (
              <tr key={l.id} className="border-t">
                <td className="py-2">{l.description}</td>
                <td className="py-2 text-right">{l.quantity}</td>
                <td className="py-2 text-right">{formatRand(l.unit_price)}</td>
                <td className="py-2 text-right">{formatRand(l.line_total ?? 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <dl className="ml-auto mt-4 w-full max-w-xs space-y-1 text-sm">
          <Row label="Subtotal" value={formatRand(doc.subtotal)} />
          {doc.discount > 0 && <Row label="Discount" value={`− ${formatRand(doc.discount)}`} />}
          {doc.tax > 0 && <Row label="Tax" value={formatRand(doc.tax)} />}
          <div className="flex justify-between border-t pt-2 text-base font-bold">
            <dt>Total</dt>
            <dd>{formatRand(doc.total)}</dd>
          </div>
          {invoice && doc.status === "issued" && (
            <>
              <Row label="Paid" value={formatRand(doc.paid)} />
              <div className="flex justify-between font-bold text-red-700">
                <dt>Balance due</dt>
                <dd>{formatRand(doc.balance)}</dd>
              </div>
            </>
          )}
        </dl>

        {doc.due_date && invoice && (
          <p className="mt-3 text-xs text-slate-500">Due {doc.due_date}</p>
        )}
        {doc.void_reason && (
          <p className="mt-3 text-sm text-red-700">Voided: {doc.void_reason}</p>
        )}
        {doc.notes && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">{doc.notes}</p>}
      </section>

      <div className="flex flex-wrap gap-3">
        <Btn icon={<Printer size={16} />} onClick={() => user && printSalesDocument(doc, user.business_id)}>
          Print
        </Btn>
        {manage && draft && (
          <>
            <Btn primary icon={<Send size={16} />} disabled={busy || !(doc.lines ?? []).length} onClick={() => act("issue")}>
              Issue
            </Btn>
            <Btn icon={<Pencil size={16} />} onClick={() => setDlg("edit")}>Edit</Btn>
            <Btn danger icon={<Trash2 size={16} />} onClick={remove}>Delete draft</Btn>
          </>
        )}
        {manage && !invoice && doc.status === "issued" && (
          <>
            <Btn primary icon={<CheckCircle2 size={16} />} disabled={busy} onClick={() => act("accept")}>
              Mark accepted
            </Btn>
            <Btn icon={<XCircle size={16} />} disabled={busy} onClick={() => act("decline")}>Mark declined</Btn>
          </>
        )}
        {manage && !invoice && doc.status === "accepted" && (
          <Btn primary icon={<FileText size={16} />} disabled={busy} onClick={() => act("convert")}>
            Convert to invoice
          </Btn>
        )}
        {manage && invoice && doc.status === "issued" && doc.balance > 0 && (
          <Btn primary icon={<CreditCard size={16} />} onClick={() => setDlg("pay")}>
            Record payment
          </Btn>
        )}
        {manage && ["issued", "accepted"].includes(doc.status) && (
          <Btn danger icon={<Ban size={16} />} onClick={() => setDlg("void")}>Void</Btn>
        )}
      </div>

      {invoice && (doc.payments ?? []).length > 0 && (
        <section className="rounded-2xl border bg-white p-5">
          <h2 className="mb-2 font-semibold">Payments</h2>
          <ul className="divide-y text-sm">
            {(doc.payments ?? []).map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-3 py-2">
                <span className={p.status === "recorded" ? "" : "text-slate-400 line-through"}>
                  {p.paid_on} · {methodLabel(p.method)}
                  {p.reference ? ` · ${p.reference}` : ""}
                </span>
                <span className="flex items-center gap-3">
                  {formatRand(p.amount)}
                  {manage && p.status === "recorded" && (
                    <button
                      type="button"
                      onClick={() => setDlg({ voidPayment: p.id })}
                      className="text-xs text-red-700 hover:underline"
                    >
                      Cancel
                    </button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {dlg === "edit" && (
        <Dialog title="Edit draft" onClose={() => setDlg(null)} wide>
          <SalesDocumentForm
            lockType
            initial={{
              customer_id: doc.customer_id,
              document_type: doc.document_type,
              lines: doc.lines ?? [],
              discount: doc.discount,
              due_date: doc.due_date,
              valid_until: doc.valid_until,
              notes: doc.notes,
            }}
            submitLabel="Save"
            onCancel={() => setDlg(null)}
            onSubmit={async (v: DocumentFormValues) => {
              const { document_type: _type, ...patch } = v;
              void _type;
              const r = await api.patch<SalesDoc>(`/sales/documents/${id}`, patch);
              setDoc(r.data);
              setDlg(null);
            }}
          />
        </Dialog>
      )}

      {dlg === "pay" && (
        <PayDialog
          balance={doc.balance}
          onClose={() => setDlg(null)}
          onSaved={(d) => {
            setDoc(d);
            setDlg(null);
          }}
          id={id}
        />
      )}

      {dlg === "void" && (
        <ReasonDialog
          title={`Void ${doc.number}`}
          onClose={() => setDlg(null)}
          onSubmit={async (reason) => {
            await act("void", { reason });
            setDlg(null);
          }}
        />
      )}

      {dlg && typeof dlg === "object" && (
        <ReasonDialog
          title="Cancel this payment"
          onClose={() => setDlg(null)}
          onSubmit={async (reason) => {
            await api.post(`/sales/payments/${dlg.voidPayment}/void`, { reason });
            setDlg(null);
            await load();
          }}
        />
      )}
    </main>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-slate-500">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function Btn({
  children,
  icon,
  onClick,
  primary,
  danger,
  disabled,
}: {
  children: React.ReactNode;
  icon: React.ReactNode;
  onClick: () => void;
  primary?: boolean;
  danger?: boolean;
  disabled?: boolean;
}) {
  const tone = primary
    ? "bg-slate-900 text-white"
    : danger
      ? "border border-red-300 text-red-700 hover:bg-red-50"
      : "border hover:bg-slate-50";
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-50 ${tone}`}
    >
      {icon}
      {children}
    </button>
  );
}

function PayDialog({
  id,
  balance,
  onClose,
  onSaved,
}: {
  id: string;
  balance: number;
  onClose: () => void;
  onSaved: (d: SalesDoc) => void;
}) {
  const [amount, setAmount] = useState(String(balance));
  const [method, setMethod] = useState("cash");
  const [reference, setReference] = useState("");
  const [paidOn, setPaidOn] = useState(today());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!(Number(amount) > 0)) return setError("Enter the amount received.");
    try {
      setSaving(true);
      const r = await api.post<SalesDoc>(`/sales/documents/${id}/payments`, {
        amount: Number(amount),
        method,
        reference: reference.trim() || null,
        paid_on: paidOn,
      });
      onSaved(r.data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not record the payment."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Record payment" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Amount received (R)</span>
          <input className={inputClass} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <select className={inputClass} value={method} onChange={(e) => setMethod(e.target.value)}>
            {METHODS.map((m) => (
              <option key={m} value={m}>{methodLabel(m)}</option>
            ))}
          </select>
          <input type="date" className={inputClass} value={paidOn} onChange={(e) => setPaidOn(e.target.value)} />
        </div>
        <input className={inputClass} placeholder="Reference (optional)" value={reference} onChange={(e) => setReference(e.target.value)} />
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Record payment" />
      </form>
    </Dialog>
  );
}

function ReasonDialog({
  title,
  onClose,
  onSubmit,
}: {
  title: string;
  onClose: () => void;
  onSubmit: (reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    const text = reason.trim();
    if (text.length < 3) return setError("Give a short reason (at least 3 letters).");
    try {
      setSaving(true);
      await onSubmit(text);
    } catch (err) {
      setError(getApiErrorMessage(err, "That did not work."));
      setSaving(false);
    }
  }

  return (
    <Dialog title={title} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        <textarea className={inputClass} rows={3} placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        <DialogFooter onClose={onClose} saving={saving} submitLabel="Confirm" danger />
      </form>
    </Dialog>
  );
}
