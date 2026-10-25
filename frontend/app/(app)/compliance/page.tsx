"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Archive, Loader2, Pencil, Plus } from "lucide-react";

import api from "@/lib/api";
import { formatDate, getApiErrorMessage } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Dialog, DialogFooter, Field, inputClass } from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";
import {
  STATE_STYLE,
  stateText,
  type ComplianceItem,
} from "@/components/dashboards/CompliancePanel";

type Item = ComplianceItem & {
  kind: string;
  issued_on: string | null;
  notes: string | null;
};

type Form = {
  kind: string;
  title: string;
  reference: string;
  issued_on: string;
  expires_on: string;
  notes: string;
};

const blank: Form = {
  kind: "certificate_of_competence",
  title: "",
  reference: "",
  issued_on: "",
  expires_on: "",
  notes: "",
};

type Dialogue =
  | { kind: "create" }
  | { kind: "edit"; item: Item }
  | { kind: "archive"; item: Item }
  | null;

export default function CompliancePage() {
  const { can } = useCurrentUser();
  const canManage = can("compliance.manage");

  const [items, setItems] = useState<Item[]>([]);
  const [kinds, setKinds] = useState<{ key: string; label: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const [dialog, setDialog] = useState<Dialogue>(null);
  const [form, setForm] = useState<Form>(blank);
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .get<{ key: string; label: string }[]>("/compliance/kinds")
      .then((r) => setKinds(r.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;

    api
      .get<{ items: Item[] }>("/compliance")
      .then((r) => {
        if (!cancelled) {
          setItems(r.data.items);
          setError("");
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(getApiErrorMessage(err, "Could not load the register."));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  function close() {
    setDialog(null);
    setDialogError("");
  }

  function openCreate() {
    setForm(blank);
    setDialogError("");
    setDialog({ kind: "create" });
  }

  function openEdit(item: Item) {
    setForm({
      kind: item.kind,
      title: item.title,
      reference: item.reference ?? "",
      issued_on: item.issued_on ?? "",
      expires_on: item.expires_on,
      notes: item.notes ?? "",
    });
    setDialogError("");
    setDialog({ kind: "edit", item });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!dialog) return;

    setSaving(true);
    setDialogError("");

    try {
      if (dialog.kind === "archive") {
        await api.post(`/compliance/${dialog.item.id}/archive`);
        setNotice("Archived. It stays in the history.");
      } else {
        const body = {
          kind: form.kind,
          title: form.title.trim(),
          reference: form.reference.trim() || null,
          issued_on: form.issued_on || null,
          expires_on: form.expires_on,
          notes: form.notes.trim() || null,
        };
        if (dialog.kind === "create") {
          await api.post("/compliance", body);
          setNotice("Added to the register.");
        } else {
          await api.patch(`/compliance/${dialog.item.id}`, body);
          setNotice("Updated.");
        }
      }
      close();
      reload();
    } catch (err) {
      setDialogError(getApiErrorMessage(err, "Could not save this."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6 md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[var(--fos-text)]">
            Licences and certificates
          </h1>
          <p className="text-sm text-[var(--fos-text-muted)]">
            What must stay valid for you to operate lawfully. The right people
            are reminded as each one gets close to expiring.
          </p>
        </div>
        {canManage && (
          <button
            type="button"
            onClick={openCreate}
            className="flex items-center gap-2 rounded-lg bg-[var(--fos-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--fos-on-primary)]"
          >
            <Plus size={16} /> Add
          </button>
        )}
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

      <div className="overflow-hidden rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)]">
        {loading ? (
          <p className="flex items-center gap-2 p-6 text-sm text-[var(--fos-text-muted)]">
            <Loader2 size={16} className="animate-spin" /> Loading…
          </p>
        ) : items.length === 0 ? (
          <p className="p-6 text-sm text-[var(--fos-text-muted)]">
            Nothing recorded yet. Add your certificate of competence first.
          </p>
        ) : (
          <ul className="divide-y divide-[var(--fos-border)]">
            {items.map((item) => (
              <li
                key={item.id}
                className="flex flex-wrap items-center gap-3 px-5 py-4"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-[var(--fos-text)]">
                    {item.title}
                  </p>
                  <p className="text-xs text-[var(--fos-text-muted)]">
                    {item.kind_label}
                    {item.reference && ` · ${item.reference}`} · expires{" "}
                    {formatDate(item.expires_on)}
                  </p>
                </div>
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATE_STYLE[item.state]}`}
                >
                  {stateText(item)}
                </span>
                {canManage && (
                  <span className="flex gap-2 text-[var(--fos-text-muted)]">
                    <button
                      type="button"
                      aria-label="Edit"
                      onClick={() => openEdit(item)}
                      className="hover:text-[var(--fos-text)]"
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      type="button"
                      aria-label="Archive"
                      onClick={() => {
                        setDialogError("");
                        setDialog({ kind: "archive", item });
                      }}
                      className="hover:text-[var(--fos-text)]"
                    >
                      <Archive size={16} />
                    </button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {dialog?.kind === "archive" && (
        <Dialog title="Archive this record" onClose={close}>
          <form onSubmit={submit} className="space-y-4">
            <p className="text-sm text-slate-600">
              {dialog.item.title} will stop appearing in reminders. Use this
              once it has been replaced by a renewed one.
            </p>
            {dialogError && <ErrorNote message={dialogError} />}
            <DialogFooter onClose={close} saving={saving} submitLabel="Archive" />
          </form>
        </Dialog>
      )}

      {dialog && dialog.kind !== "archive" && (
        <Dialog
          title={dialog.kind === "create" ? "Add a licence or certificate" : "Edit"}
          onClose={close}
        >
          <form onSubmit={submit} className="space-y-4">
            <Field label="Kind">
              <select
                className={inputClass}
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value })}
              >
                {kinds.map((k) => (
                  <option key={k.key} value={k.key}>
                    {k.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Name">
              <input
                required
                minLength={2}
                className={inputClass}
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </Field>
            <Field label="Reference or number">
              <input
                className={inputClass}
                value={form.reference}
                onChange={(e) =>
                  setForm({ ...form, reference: e.target.value })
                }
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Issued on">
                <input
                  type="date"
                  className={inputClass}
                  value={form.issued_on}
                  onChange={(e) =>
                    setForm({ ...form, issued_on: e.target.value })
                  }
                />
              </Field>
              <Field label="Expires on">
                <input
                  required
                  type="date"
                  className={inputClass}
                  value={form.expires_on}
                  onChange={(e) =>
                    setForm({ ...form, expires_on: e.target.value })
                  }
                />
              </Field>
            </div>
            <Field label="Notes (optional)">
              <textarea
                rows={2}
                className={inputClass}
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </Field>
            {dialogError && <ErrorNote message={dialogError} />}
            <DialogFooter
              onClose={close}
              saving={saving}
              submitLabel={dialog.kind === "create" ? "Add" : "Save changes"}
            />
          </form>
        </Dialog>
      )}
    </div>
  );
}
