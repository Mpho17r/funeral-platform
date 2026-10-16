"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  Building,
  Crown,
  Loader2,
  Mail,
  MapPin,
  Pencil,
  Phone,
  Plus,
  Power,
  PowerOff,
} from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage, statusOf } from "@/lib/format";
import type { Branch, BranchSummary } from "@/lib/branches";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";

/* ============================================================
   TYPES
============================================================ */

type Dialogue =
  | { kind: "create" }
  | { kind: "edit"; branch: Branch }
  | { kind: "deactivate"; branch: Branch }
  | { kind: "make-main"; branch: Branch }
  | null;

type BranchBody = {
  name: string;
  code: string;
  phone: string | null;
  email: string | null;
  address: string | null;
  notes: string | null;
};

/* ============================================================
   PAGE
============================================================ */

export default function BranchesPage() {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [summaries, setSummaries] = useState<
    Map<string, BranchSummary>
  >(new Map());

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showInactive, setShowInactive] = useState(false);

  const [dialog, setDialog] = useState<Dialogue>(null);
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  // Bumping this refetches everything after a change.
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadAll() {
      let list: Branch[];

      try {
        const response = await api.get<Branch[]>("/branches", {
          params: { include_inactive: true },
        });

        list = response.data;
      } catch (err) {
        if (!cancelled) {
          setError(
            statusOf(err) === 401
              ? "Your session has expired. Please log in again."
              : getApiErrorMessage(err, "Failed to load branches.")
          );
          setLoading(false);
        }

        return;
      }

      if (cancelled) {
        return;
      }

      setBranches(list);
      setError("");

      // Counts are an extra. A card still works without them.
      const results = await Promise.allSettled(
        list.map((branch) =>
          api.get<BranchSummary>(`/branches/${branch.id}/summary`)
        )
      );

      if (cancelled) {
        return;
      }

      const next = new Map<string, BranchSummary>();

      results.forEach((result) => {
        if (result.status === "fulfilled") {
          next.set(result.value.data.branch_id, result.value.data);
        }
      });

      setSummaries(next);
      setLoading(false);
    }

    loadAll();

    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function reload() {
    setReloadKey((current) => current + 1);
  }

  function closeDialog() {
    setDialog(null);
    setDialogError("");
  }

  async function runAction(
    request: () => Promise<unknown>,
    done: string
  ) {
    setSaving(true);
    setDialogError("");

    try {
      await request();

      closeDialog();
      setNotice(done);
      reload();
    } catch (err) {
      setDialogError(
        getApiErrorMessage(err, "Something went wrong.")
      );
    } finally {
      setSaving(false);
    }
  }

  const inactiveCount = branches.filter(
    (branch) => !branch.is_active
  ).length;

  const visible = branches.filter(
    (branch) => showInactive || branch.is_active
  );

  /* ---------------- render ---------------- */

  return (
    <div className="space-y-6 p-6 md:p-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Branches
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Everyone can see every branch. A branch groups cases,
            members, resources and staff so you can filter by it.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setDialogError("");
            setDialog({ kind: "create" });
          }}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800"
        >
          <Plus size={18} />
          Add Branch
        </button>
      </div>

      {error && (
        <Banner tone="error" onDismiss={() => setError("")}>
          {error}
        </Banner>
      )}

      {notice && (
        <Banner tone="success" onDismiss={() => setNotice("")}>
          {notice}
        </Banner>
      )}

      {inactiveCount > 0 && (
        <label className="flex items-center justify-end gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(event) =>
              setShowInactive(event.target.checked)
            }
            className="h-4 w-4 rounded border-slate-300"
          />
          Show inactive ({inactiveCount})
        </label>
      )}

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-gray-500">
          <Loader2 size={18} className="animate-spin" />
          Loading branches…
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white px-6 py-14 text-center">
          <Building size={32} className="mx-auto text-gray-400" />
          <p className="mt-3 text-sm font-medium text-gray-700">
            No branches yet. Add your first branch.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((branch) => (
            <BranchCard
              key={branch.id}
              branch={branch}
              summary={summaries.get(branch.id)}
              onEdit={() => {
                setDialogError("");
                setDialog({ kind: "edit", branch });
              }}
              onMakeMain={() => {
                setDialogError("");
                setDialog({ kind: "make-main", branch });
              }}
              onToggle={() => {
                setDialogError("");

                if (branch.is_active) {
                  setDialog({ kind: "deactivate", branch });
                } else {
                  runAction(
                    () =>
                      api.post(`/branches/${branch.id}/reactivate`),
                    `${branch.name} is active again.`
                  );
                }
              }}
            />
          ))}
        </div>
      )}

      {dialog?.kind === "create" && (
        <BranchDialog
          saving={saving}
          error={dialogError}
          onClose={closeDialog}
          onSubmit={(body) =>
            runAction(
              () => api.post("/branches", body),
              `${body.name} added.`
            )
          }
        />
      )}

      {dialog?.kind === "edit" && (
        <BranchDialog
          branch={dialog.branch}
          saving={saving}
          error={dialogError}
          onClose={closeDialog}
          onSubmit={(body) =>
            runAction(
              () =>
                api.patch(`/branches/${dialog.branch.id}`, body),
              `${body.name} updated.`
            )
          }
        />
      )}

      {dialog?.kind === "make-main" && (
        <Dialog
          title={`Make ${dialog.branch.name} the main branch?`}
          onClose={closeDialog}
        >
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              runAction(
                () =>
                  api.post(`/branches/${dialog.branch.id}/make-main`),
                `${dialog.branch.name} is now the main branch.`
              );
            }}
          >
            <p className="text-sm text-slate-600">
              New records go to the main branch when the person
              creating them has no branch of their own. Only one
              branch can be the main branch, so the current one
              stops being it.
            </p>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              submitLabel="Make main branch"
            />
          </form>
        </Dialog>
      )}

      {dialog?.kind === "deactivate" && (
        <Dialog
          title={`Deactivate ${dialog.branch.name}?`}
          onClose={closeDialog}
        >
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              runAction(
                () =>
                  api.post(`/branches/${dialog.branch.id}/deactivate`),
                `${dialog.branch.name} deactivated.`
              );
            }}
          >
            <p className="text-sm text-slate-600">
              It can no longer receive new records. Records already
              in it stay there, and you can reactivate it at any
              time. A branch with live cases cannot be deactivated
              until they are moved or finished.
            </p>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              submitLabel="Deactivate"
              danger
            />
          </form>
        </Dialog>
      )}
    </div>
  );
}

/* ============================================================
   BRANCH CARD
============================================================ */

function BranchCard({
  branch,
  summary,
  onEdit,
  onMakeMain,
  onToggle,
}: {
  branch: Branch;
  summary: BranchSummary | undefined;
  onEdit: () => void;
  onMakeMain: () => void;
  onToggle: () => void;
}) {
  return (
    <article
      className={`flex flex-col rounded-xl border border-gray-200 bg-white p-5 shadow-sm ${
        branch.is_active ? "" : "opacity-70"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="rounded-lg bg-slate-100 p-2.5 text-slate-600">
          <Building size={20} />
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-base font-semibold text-slate-900">
              {branch.name}
            </h3>

            {branch.is_main && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
                <Crown size={12} />
                Main
              </span>
            )}

            {!branch.is_active && (
              <span className="rounded-full bg-slate-200 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                Inactive
              </span>
            )}
          </div>

          <p className="mt-0.5 text-xs font-medium uppercase tracking-wide text-slate-400">
            {branch.code}
          </p>
        </div>
      </div>

      <dl className="mt-4 space-y-1.5 text-sm text-slate-600">
        {branch.phone && (
          <div className="flex items-center gap-2">
            <Phone size={14} className="shrink-0 text-slate-400" />
            <dd>{branch.phone}</dd>
          </div>
        )}

        {branch.email && (
          <div className="flex items-center gap-2">
            <Mail size={14} className="shrink-0 text-slate-400" />
            <dd className="truncate">{branch.email}</dd>
          </div>
        )}

        {branch.address && (
          <div className="flex items-start gap-2">
            <MapPin
              size={14}
              className="mt-0.5 shrink-0 text-slate-400"
            />
            <dd>{branch.address}</dd>
          </div>
        )}
      </dl>

      {branch.notes && (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
          {branch.notes}
        </p>
      )}

      {summary && (
        <dl className="mt-4 grid grid-cols-2 gap-2 text-center">
          <Count label="Live cases" value={summary.live_cases} />
          <Count label="All cases" value={summary.total_cases} />
          <Count label="Members" value={summary.members} />
          <Count label="Staff" value={summary.active_staff} />
          <Count
            label="Resources"
            value={summary.active_resources}
          />
        </dl>
      )}

      <div className="mt-auto flex flex-wrap gap-2 pt-5">
        <button
          type="button"
          onClick={onEdit}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          <Pencil size={14} />
          Edit
        </button>

        {branch.is_active && !branch.is_main && (
          <button
            type="button"
            onClick={onMakeMain}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            <Crown size={14} />
            Make main
          </button>
        )}

        {!branch.is_main && (
          <button
            type="button"
            onClick={onToggle}
            className={`ml-auto inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ${
              branch.is_active
                ? "text-red-600 hover:bg-red-50"
                : "text-emerald-700 hover:bg-emerald-50"
            }`}
          >
            {branch.is_active ? (
              <>
                <PowerOff size={14} />
                Deactivate
              </>
            ) : (
              <>
                <Power size={14} />
                Reactivate
              </>
            )}
          </button>
        )}
      </div>
    </article>
  );
}

function Count({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-slate-50 px-2 py-2">
      <dd className="text-lg font-semibold text-slate-900">
        {value}
      </dd>
      <dt className="text-xs text-slate-500">{label}</dt>
    </div>
  );
}

/* ============================================================
   ADD / EDIT DIALOG
============================================================ */

function BranchDialog({
  branch,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  branch?: Branch;
  saving: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (body: BranchBody) => void;
}) {
  const [name, setName] = useState(branch?.name ?? "");
  const [code, setCode] = useState(branch?.code ?? "");
  const [phone, setPhone] = useState(branch?.phone ?? "");
  const [email, setEmail] = useState(branch?.email ?? "");
  const [address, setAddress] = useState(branch?.address ?? "");
  const [notes, setNotes] = useState(branch?.notes ?? "");

  const editing = Boolean(branch);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();

    onSubmit({
      name: name.trim(),
      code: code.trim().toUpperCase(),
      phone: phone.trim() || null,
      email: email.trim() || null,
      address: address.trim() || null,
      notes: notes.trim() || null,
    });
  }

  return (
    <Dialog
      title={editing ? `Edit ${branch?.name}` : "Add Branch"}
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
          <Field label="Name">
            <input
              required
              maxLength={150}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Soweto Branch"
              className={inputClass}
            />
          </Field>

          <Field label="Code" hint="2–10 letters or numbers.">
            <input
              required
              maxLength={10}
              value={code}
              onChange={(event) =>
                setCode(event.target.value.toUpperCase())
              }
              placeholder="SOW"
              className={inputClass}
            />
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Phone (optional)">
            <input
              maxLength={30}
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              className={inputClass}
            />
          </Field>

          <Field label="Email (optional)">
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={inputClass}
            />
          </Field>
        </div>

        <Field label="Address (optional)">
          <textarea
            rows={2}
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Notes (optional)">
          <textarea
            rows={3}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className={inputClass}
          />
        </Field>

        {error && <ErrorNote message={error} />}

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel={editing ? "Save changes" : "Add branch"}
          disabled={!name.trim() || !code.trim()}
        />
      </form>
    </Dialog>
  );
}
