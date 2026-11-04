"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Archive, Download, FileText, FolderOpen, Plus, RotateCcw } from "lucide-react";

import api from "@/lib/api";
import { categoryLabel, getApiErrorMessage } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, inputClass } from "@/components/Dialog";
import { ErrorNote } from "@/components/Notices";

type Doc = {
  id: string;
  title: string;
  category: string;
  customer_id: string | null;
  customer_name: string | null;
  notes: string | null;
  expires_on: string | null;
  expiry: "expired" | "soon" | null;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_by_name: string | null;
  archived: boolean;
  created_at: string;
};

type Listing = {
  items: Doc[];
  categories: string[];
  counts: { total: number; expired: number; soon: number };
};

type CustomerOption = { id: string; name: string };

const size = (bytes: number) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;

export default function DocumentsPage() {
  const { can } = useCurrentUser();
  const manage = can("library.manage");

  const [data, setData] = useState<Listing | null>(null);
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [expiring, setExpiring] = useState(false);
  const [archived, setArchived] = useState(false);
  const [editing, setEditing] = useState<Doc | "new" | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await api.get<Listing>("/library", {
        params: {
          q: search.trim() || undefined,
          category: category || undefined,
          expiring: expiring || undefined,
          archived: archived || undefined,
        },
      });
      setData(r.data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load documents."));
    }
  }, [search, category, expiring, archived]);

  useEffect(() => {
    const t = setTimeout(() => void load(), 200);
    return () => clearTimeout(t);
  }, [load]);

  useEffect(() => {
    if (!manage) return;
    api
      .get<{ items: CustomerOption[] }>("/customers")
      .then((r) => setCustomers(r.data.items))
      .catch(() => undefined);
  }, [manage]);

  async function open(doc: Doc) {
    try {
      const r = await api.get(`/library/${doc.id}/file`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = doc.file_name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not download the file."));
    }
  }

  async function act(doc: Doc, action: "archive" | "restore") {
    try {
      setError("");
      await api.post(`/library/${doc.id}/${action}`, {});
      await load();
    } catch (err) {
      setError(getApiErrorMessage(err, "That did not work."));
    }
  }

  return (
    <main className="mx-auto max-w-4xl space-y-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-[var(--fos-primary)] p-3 text-[var(--fos-on-primary)]">
            <FolderOpen size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Documents</h1>
            <p className="text-sm text-slate-500">Contracts, licences, receipts and other papers, in one place.</p>
          </div>
        </div>
        {manage && (
          <button
            type="button"
            onClick={() => setEditing("new")}
            className="flex items-center gap-2 rounded-lg bg-[var(--fos-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--fos-on-primary)]"
          >
            <Plus size={16} /> Add document
          </button>
        )}
      </header>

      {error && <ErrorNote message={error} />}

      {data && (data.counts.expired > 0 || data.counts.soon > 0) && (
        <button
          type="button"
          onClick={() => setExpiring((v) => !v)}
          className="w-full rounded-xl border border-amber-300 bg-amber-50 p-3 text-left text-sm text-amber-900"
        >
          {data.counts.expired > 0 && <strong>{data.counts.expired} expired</strong>}
          {data.counts.expired > 0 && data.counts.soon > 0 && " · "}
          {data.counts.soon > 0 && <strong>{data.counts.soon} expiring within 30 days</strong>}
          <span className="ml-2 underline">{expiring ? "Show all" : "Show only these"}</span>
        </button>
      )}

      <section className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-3">
        <input
          className="min-w-40 flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          placeholder="Search title, file or notes"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Every type</option>
          {(data?.categories ?? []).map((c) => (
            <option key={c} value={c}>
              {categoryLabel(c)}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} /> Archived
        </label>
      </section>

      {!data ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : data.items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">
          <FileText className="mx-auto mb-2" />
          {archived ? "Nothing is archived." : "No documents yet."}
        </div>
      ) : (
        data.items.map((d) => (
          <article key={d.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="font-semibold">{d.title}</p>
                <p className="text-sm text-slate-500">
                  {categoryLabel(d.category)} · {d.file_name} · {size(d.size_bytes)}
                  {d.customer_name ? ` · ${d.customer_name}` : ""}
                </p>
                {d.notes && <p className="mt-1 text-sm text-slate-600">{d.notes}</p>}
                <p className="mt-1 text-xs text-slate-400">
                  Added {new Date(d.created_at).toLocaleDateString("en-ZA")}
                  {d.uploaded_by_name ? ` by ${d.uploaded_by_name}` : ""}
                </p>
              </div>
              {d.expires_on && (
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                    d.expiry === "expired"
                      ? "bg-red-100 text-red-800"
                      : d.expiry === "soon"
                        ? "bg-amber-100 text-amber-800"
                        : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {d.expiry === "expired" ? "Expired " : "Expires "}
                  {d.expires_on}
                </span>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              <button type="button" className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5" onClick={() => void open(d)}>
                <Download size={14} /> Download
              </button>
              {manage && !d.archived && (
                <>
                  <button type="button" className="rounded-lg border border-slate-300 px-3 py-1.5" onClick={() => setEditing(d)}>
                    Details
                  </button>
                  <button type="button" className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5" onClick={() => void act(d, "archive")}>
                    <Archive size={14} /> Archive
                  </button>
                </>
              )}
              {manage && d.archived && (
                <button type="button" className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5" onClick={() => void act(d, "restore")}>
                  <RotateCcw size={14} /> Restore
                </button>
              )}
            </div>
          </article>
        ))
      )}

      {editing && data && (
        <DocDialog
          existing={editing === "new" ? null : editing}
          categories={data.categories}
          customers={customers}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void load();
          }}
        />
      )}
    </main>
  );
}

function DocDialog({
  existing,
  categories,
  customers,
  onClose,
  onSaved,
}: {
  existing: Doc | null;
  categories: string[];
  customers: CustomerOption[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState(existing?.title ?? "");
  const [category, setCategory] = useState(existing?.category ?? "other");
  const [customerId, setCustomerId] = useState(existing?.customer_id ?? "");
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [expires, setExpires] = useState(existing?.expires_on ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      setSaving(true);
      setError("");
      if (existing) {
        await api.patch(`/library/${existing.id}`, {
          title: title.trim(),
          category,
          customer_id: customerId || null,
          notes: notes.trim() || null,
          expires_on: expires || null,
        });
      } else {
        if (!file) {
          setError("Choose a file to add.");
          return;
        }
        const form = new FormData();
        form.append("file", file);
        if (title.trim()) form.append("title", title.trim());
        form.append("category", category);
        if (customerId) form.append("customer_id", customerId);
        if (notes.trim()) form.append("notes", notes.trim());
        if (expires) form.append("expires_on", expires);
        await api.post("/library", form);
      }
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save the document."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={existing ? "Document details" : "Add a document"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorNote message={error} />}
        {!existing && (
          <input
            type="file"
            className={inputClass}
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
              if (f && !title) setTitle(f.name.replace(/\.[^.]+$/, ""));
            }}
          />
        )}
        <input className={inputClass} placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <select className={inputClass} value={category} onChange={(e) => setCategory(e.target.value)}>
          {categories.map((c) => (
            <option key={c} value={c}>
              {categoryLabel(c)}
            </option>
          ))}
        </select>
        {customers.length > 0 && (
          <select className={inputClass} value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">Not about one customer</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}
        <label className="block text-xs text-slate-500">
          Expires on (optional: you will be told before it does)
          <input type="date" className={inputClass} value={expires} onChange={(e) => setExpires(e.target.value)} />
        </label>
        <textarea className={inputClass} rows={2} placeholder="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
        <DialogFooter onClose={onClose} saving={saving} submitLabel={existing ? "Save" : "Add"} />
      </form>
    </Dialog>
  );
}
