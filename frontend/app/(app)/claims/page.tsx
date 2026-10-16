"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleDollarSign,
  ClipboardCheck,
  Eye,
  Loader2,
  Pencil,
  Plus,
  ShieldAlert,
  ShieldCheck,
  XCircle,
  X,
} from "lucide-react";
import Link from "next/link";

import api from "@/lib/api";
import {
  formatDate,
  formatMoney,
  formatPercent,
  formatStatus,
  getApiErrorMessage,
  statusOf,
} from "@/lib/format";
import {
  Dialog,
  DialogFooter,
  Field,
  inputClass,
} from "@/components/Dialog";

/* ============================================================
   TYPES
   Money arrives as decimal strings; Number() is for display only.
============================================================ */

type CoverageBenefit = {
  benefit_id: string;
  name: string;
  benefit_type: string;
  monetary_limit: string | null;
  quantity_limit: number | null;
  is_included: boolean;
};

type CoverageSnapshot = {
  evaluated_at: string;
  covered: boolean;
  reason: string;
  plan_name: string | null;
  benefits: CoverageBenefit[];
};

type PayoutAllocation = {
  beneficiary_id: string;
  name: string;
  relationship: string;
  share_percent: string;
  amount: string;
};

type Claim = {
  id: string;
  claim_number: string;
  membership_id: string;
  case_id: string;
  status: string;
  claimed_amount: string;
  approved_amount: string | null;
  submission_coverage: CoverageSnapshot | null;
  decision_coverage: CoverageSnapshot | null;
  override_used: boolean;
  decision_reason: string | null;
  decided_at: string | null;
  paid_at: string | null;
  payment_reference: string | null;
  payout_allocations: PayoutAllocation[] | null;
  notes: string | null;
  created_at: string;
};

type FuneralCase = {
  id: string;
  case_number: string;
  deceased_full_name: string;
  membership_id: string | null;
};

type Membership = {
  id: string;
  member_id: string;
  membership_number: string;
};

type Member = {
  id: string;
  first_name: string;
  last_name: string;
};

type Dialogs =
  | { kind: "submit" }
  | { kind: "edit"; claim: Claim }
  | { kind: "approve"; claim: Claim }
  | { kind: "reject"; claim: Claim }
  | { kind: "pay"; claim: Claim }
  | { kind: "cancel"; claim: Claim }
  | null;

type Filter =
  | "all"
  | "submitted"
  | "under_review"
  | "approved"
  | "paid"
  | "rejected"
  | "cancelled";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "submitted", label: "Submitted" },
  { value: "under_review", label: "Under review" },
  { value: "approved", label: "Approved" },
  { value: "paid", label: "Paid" },
  { value: "rejected", label: "Rejected" },
  { value: "cancelled", label: "Cancelled" },
];

// Mirrors the server: a case may hold one claim in any of these.
const LIVE_STATUSES = [
  "submitted",
  "under_review",
  "approved",
  "paid",
];

const STATUS_STYLE: Record<string, string> = {
  submitted: "bg-sky-50 text-sky-700",
  under_review: "bg-amber-50 text-amber-700",
  approved: "bg-emerald-50 text-emerald-700",
  paid: "bg-indigo-50 text-indigo-700",
  rejected: "bg-red-50 text-red-700",
  cancelled: "bg-gray-100 text-gray-600",
};

/* ============================================================
   PAGE
============================================================ */

export default function ClaimsPage() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [cases, setCases] = useState<FuneralCase[]>([]);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [members, setMembers] = useState<Member[]>([]);

  const [filter, setFilter] = useState<Filter>("all");
  const [openId, setOpenId] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [dialog, setDialog] = useState<Dialogs>(null);
  const [saving, setSaving] = useState(false);
  const [dialogError, setDialogError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  /* ---------------- load ---------------- */

  // Bumping this refetches everything after a change.
  const [reloadKey, setReloadKey] = useState(0);

  function reload() {
    setReloadKey((current) => current + 1);
  }

  useEffect(() => {
    let cancelled = false;

    async function loadAll() {
      try {
        const [
          claimsResponse,
          casesResponse,
          membershipsResponse,
          membersResponse,
        ] = await Promise.all([
          api.get<Claim[]>("/claims"),
          api.get<FuneralCase[]>("/cases"),
          api.get<Membership[]>("/memberships"),
          api.get<Member[]>("/members"),
        ]);

        if (cancelled) {
          return;
        }

        setClaims(claimsResponse.data);
        setCases(casesResponse.data);
        setMemberships(membershipsResponse.data);
        setMembers(membersResponse.data);
        setError("");
      } catch (err) {
        if (!cancelled) {
          setError(
            statusOf(err) === 401
              ? "Your session has expired. Please log in again."
              : getApiErrorMessage(err, "Failed to load claims.")
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadAll();

    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  /* ---------------- lookups ---------------- */

  const caseById = useMemo(
    () => new Map(cases.map((item) => [item.id, item])),
    [cases]
  );

  const membershipLabel = useMemo(() => {
    const names = new Map(
      members.map((member) => [
        member.id,
        `${member.first_name} ${member.last_name}`,
      ])
    );

    return new Map(
      memberships.map((membership) => {
        const name = names.get(membership.member_id);

        return [
          membership.id,
          name
            ? `${membership.membership_number} · ${name}`
            : membership.membership_number,
        ];
      })
    );
  }, [memberships, members]);

  const visible = claims.filter(
    (claim) => filter === "all" || claim.status === filter
  );

  const counts = useMemo(() => {
    const result: Record<string, number> = { all: claims.length };

    for (const claim of claims) {
      result[claim.status] = (result[claim.status] ?? 0) + 1;
    }

    return result;
  }, [claims]);

  // Cases a new claim could be raised on.
  const claimableCases = useMemo(() => {
    const taken = new Set(
      claims
        .filter((claim) => LIVE_STATUSES.includes(claim.status))
        .map((claim) => claim.case_id)
    );

    return cases.filter(
      (item) => item.membership_id && !taken.has(item.id)
    );
  }, [cases, claims]);

  /* ---------------- actions ---------------- */

  function closeDialog() {
    setDialog(null);
    setDialogError("");
  }

  async function runAction(
    path: string,
    body: Record<string, unknown> | undefined,
    done: string
  ) {
    setSaving(true);
    setDialogError("");

    try {
      await api.post(path, body);

      closeDialog();
      setNotice(done);
      reload();
    } catch (err) {
      setDialogError(
        getApiErrorMessage(err, "That action could not be completed.")
      );
    } finally {
      setSaving(false);
    }
  }

  async function startReview(claim: Claim) {
    setBusyId(claim.id);
    setError("");

    try {
      await api.post(`/claims/${claim.id}/review`);

      setNotice(`${claim.claim_number} is now under review.`);
      reload();
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Unable to start the review.")
      );
    } finally {
      setBusyId(null);
    }
  }

  /* ============================================================
     RENDER
  ============================================================ */

  return (
    <div className="space-y-6 p-6 md:p-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Claims</h1>
          <p className="mt-1 text-sm text-gray-500">
            Funeral cover claims, from submission to payout.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setDialogError("");
            setDialog({ kind: "submit" });
          }}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800"
        >
          <Plus size={18} />
          Submit Claim
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

      <div
        className="flex flex-wrap gap-2"
        role="tablist"
        aria-label="Filter claims by status"
      >
        {FILTERS.map((item) => (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={filter === item.value}
            onClick={() => setFilter(item.value)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
              filter === item.value
                ? "bg-slate-900 text-white"
                : "bg-white text-slate-600 hover:bg-slate-100"
            }`}
          >
            {item.label}
            <span
              className={`ml-1.5 text-xs ${
                filter === item.value
                  ? "text-slate-300"
                  : "text-slate-400"
              }`}
            >
              {counts[item.value] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-gray-500">
          <Loader2 size={18} className="animate-spin" />
          Loading claims…
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white px-6 py-14 text-center">
          <ClipboardCheck
            size={32}
            className="mx-auto text-gray-400"
          />
          <p className="mt-3 text-sm font-medium text-gray-700">
            {claims.length === 0
              ? "No claims yet."
              : "No claims with this status."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {visible.map((claim) => (
            <ClaimCard
              key={claim.id}
              claim={claim}
              caseInfo={caseById.get(claim.case_id)}
              membershipText={
                membershipLabel.get(claim.membership_id) ??
                "Unknown membership"
              }
              open={openId === claim.id}
              busy={busyId === claim.id}
              onToggle={() =>
                setOpenId(openId === claim.id ? null : claim.id)
              }
              onReview={() => startReview(claim)}
              onOpenDialog={(kind) => {
                setDialogError("");
                setDialog({ kind, claim });
              }}
            />
          ))}
        </div>
      )}

      {dialog?.kind === "submit" && (
        <SubmitDialog
          cases={claimableCases}
          saving={saving}
          error={dialogError}
          onClose={closeDialog}
          onSubmit={(caseId, amount, notes) =>
            runAction(
              "/claims",
              {
                case_id: caseId,
                claimed_amount: amount,
                notes: notes.trim() || null,
              },
              "Claim submitted."
            )
          }
        />
      )}

      {dialog?.kind === "edit" && (
        <EditDialog
          claim={dialog.claim}
          saving={saving}
          error={dialogError}
          onClose={closeDialog}
          onSubmit={async (amount, notes) => {
            setSaving(true);
            setDialogError("");

            try {
              await api.patch(`/claims/${dialog.claim.id}`, {
                claimed_amount: amount,
                notes: notes.trim() || null,
              });

              closeDialog();
              setNotice("Claim updated.");
              reload();
            } catch (err) {
              setDialogError(
                getApiErrorMessage(err, "Unable to update the claim.")
              );
            } finally {
              setSaving(false);
            }
          }}
        />
      )}

      {dialog?.kind === "approve" && (
        <ApproveDialog
          claim={dialog.claim}
          saving={saving}
          error={dialogError}
          onClose={closeDialog}
          onSubmit={(amount, note, overrideReason) =>
            runAction(
              `/claims/${dialog.claim.id}/approve`,
              {
                approved_amount: amount,
                note: note.trim() || null,
                override_reason: overrideReason.trim() || null,
              },
              `${dialog.claim.claim_number} approved.`
            )
          }
        />
      )}

      {dialog?.kind === "reject" && (
        <TextDialog
          title="Reject claim"
          label="Reason for rejecting"
          hint="Shown on the claim and kept in the audit trail."
          required
          submitLabel="Reject claim"
          danger
          saving={saving}
          error={dialogError}
          onClose={closeDialog}
          onSubmit={(value) =>
            runAction(
              `/claims/${dialog.claim.id}/reject`,
              { reason: value.trim() },
              `${dialog.claim.claim_number} rejected.`
            )
          }
        />
      )}

      {dialog?.kind === "cancel" && (
        <TextDialog
          title="Cancel claim"
          label="Reason (optional)"
          submitLabel="Cancel claim"
          danger
          saving={saving}
          error={dialogError}
          onClose={closeDialog}
          onSubmit={(value) =>
            runAction(
              `/claims/${dialog.claim.id}/cancel`,
              { reason: value.trim() || null },
              `${dialog.claim.claim_number} cancelled.`
            )
          }
        />
      )}

      {dialog?.kind === "pay" && (
        <TextDialog
          title="Mark claim as paid"
          label="Payment reference"
          hint={`R ${formatMoney(
            dialog.claim.approved_amount
          )} is split between the beneficiaries by share.`}
          required
          single
          submitLabel="Mark as paid"
          saving={saving}
          error={dialogError}
          onClose={closeDialog}
          onSubmit={(value) =>
            runAction(
              `/claims/${dialog.claim.id}/pay`,
              { payment_reference: value.trim() },
              `${dialog.claim.claim_number} marked as paid.`
            )
          }
          footer={
            <Link
              href={`/beneficiaries?membership=${dialog.claim.membership_id}`}
              className="text-xs font-medium text-slate-600 underline"
            >
              Check beneficiary shares
            </Link>
          }
        />
      )}
    </div>
  );
}

/* ============================================================
   CLAIM CARD
============================================================ */

function ClaimCard({
  claim,
  caseInfo,
  membershipText,
  open,
  busy,
  onToggle,
  onReview,
  onOpenDialog,
}: {
  claim: Claim;
  caseInfo: FuneralCase | undefined;
  membershipText: string;
  open: boolean;
  busy: boolean;
  onToggle: () => void;
  onReview: () => void;
  onOpenDialog: (
    kind: "edit" | "approve" | "reject" | "pay" | "cancel"
  ) => void;
}) {
  const awaitingDecision =
    claim.status === "submitted" || claim.status === "under_review";

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-4 px-5 py-4 text-left hover:bg-slate-50"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-base font-bold text-slate-900">
              {claim.claim_number}
            </span>

            <StatusBadge status={claim.status} />

            {claim.override_used && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
                <ShieldAlert size={12} />
                Override
              </span>
            )}
          </div>

          <p className="mt-1 truncate text-xs text-slate-500">
            {caseInfo
              ? `Case ${caseInfo.case_number} · ${caseInfo.deceased_full_name}`
              : "Case unavailable (archived or removed)"}
            {" · "}
            {membershipText}
          </p>
        </div>

        <div className="text-right">
          <p className="text-base font-bold text-slate-900">
            R {formatMoney(claim.approved_amount ?? claim.claimed_amount)}
          </p>

          <p className="text-xs text-slate-500">
            {claim.approved_amount !== null
              ? `of R ${formatMoney(claim.claimed_amount)} claimed`
              : "claimed"}
          </p>
        </div>

        {open ? (
          <ChevronUp size={18} className="text-slate-400" />
        ) : (
          <ChevronDown size={18} className="text-slate-400" />
        )}
      </button>

      {open && (
        <div className="space-y-5 border-t border-slate-200 px-5 py-5">
          {claim.override_used && (
            <div className="flex gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <ShieldAlert size={18} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-semibold">
                  Approved with an override
                </p>
                <p className="mt-0.5">
                  {claim.decision_reason ?? "No reason recorded."}
                </p>
              </div>
            </div>
          )}

          {!claim.override_used &&
            claim.decision_reason &&
            (claim.status === "rejected" ||
              claim.status === "cancelled" ||
              claim.status === "approved" ||
              claim.status === "paid") && (
              <p className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-700">
                <span className="font-semibold">
                  {claim.status === "rejected"
                    ? "Reason for rejection: "
                    : claim.status === "cancelled"
                    ? "Reason for cancelling: "
                    : "Decision note: "}
                </span>
                {claim.decision_reason}
              </p>
            )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <CoveragePanel
              title="Cover at submission"
              snapshot={claim.submission_coverage}
            />

            <CoveragePanel
              title="Cover at decision"
              snapshot={claim.decision_coverage}
              emptyText="Not decided yet."
            />
          </div>

          {claim.status === "paid" && (
            <PayoutPanel claim={claim} />
          )}

          {claim.notes && (
            <p className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600">
              {claim.notes}
            </p>
          )}

          <p className="text-xs text-slate-400">
            Submitted {formatDate(claim.created_at)}
            {claim.decided_at &&
              ` · Decided ${formatDate(claim.decided_at)}`}
            {claim.paid_at && ` · Paid ${formatDate(claim.paid_at)}`}
          </p>

          {(awaitingDecision || claim.status === "approved") && (
            <div className="flex flex-wrap gap-3 border-t border-slate-200 pt-4">
              {claim.status === "submitted" && (
                <ActionButton
                  primary
                  disabled={busy}
                  onClick={onReview}
                  icon={
                    busy ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <Eye size={16} />
                    )
                  }
                >
                  Start review
                </ActionButton>
              )}

              {claim.status === "under_review" && (
                <>
                  <ActionButton
                    primary
                    onClick={() => onOpenDialog("approve")}
                    icon={<CheckCircle2 size={16} />}
                  >
                    Approve
                  </ActionButton>

                  <ActionButton
                    onClick={() => onOpenDialog("reject")}
                    icon={<XCircle size={16} />}
                  >
                    Reject
                  </ActionButton>
                </>
              )}

              {claim.status === "approved" && (
                <ActionButton
                  primary
                  onClick={() => onOpenDialog("pay")}
                  icon={<CircleDollarSign size={16} />}
                >
                  Mark as paid
                </ActionButton>
              )}

              {awaitingDecision && (
                <ActionButton
                  onClick={() => onOpenDialog("edit")}
                  icon={<Pencil size={16} />}
                >
                  Edit
                </ActionButton>
              )}

              <ActionButton
                danger
                onClick={() => onOpenDialog("cancel")}
                icon={<Ban size={16} />}
              >
                Cancel claim
              </ActionButton>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ============================================================
   PANELS
============================================================ */

function CoveragePanel({
  title,
  snapshot,
  emptyText = "No cover check recorded.",
}: {
  title: string;
  snapshot: CoverageSnapshot | null;
  emptyText?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {title}
      </h3>

      {!snapshot ? (
        <p className="mt-3 text-sm text-slate-400">{emptyText}</p>
      ) : (
        <>
          <p
            className={`mt-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
              snapshot.covered
                ? "bg-emerald-50 text-emerald-700"
                : "bg-red-50 text-red-700"
            }`}
          >
            {snapshot.covered ? (
              <ShieldCheck size={13} />
            ) : (
              <AlertTriangle size={13} />
            )}
            {snapshot.covered ? "Covered" : "Not covered"}
          </p>

          <p className="mt-2 text-sm text-slate-600">
            {snapshot.reason}
          </p>

          {snapshot.plan_name && (
            <p className="mt-1 text-xs text-slate-400">
              Plan: {snapshot.plan_name}
            </p>
          )}

          {snapshot.benefits.length > 0 && (
            <ul className="mt-3 divide-y divide-slate-100 text-sm">
              {snapshot.benefits.map((benefit) => (
                <li
                  key={benefit.benefit_id}
                  className="flex items-center justify-between py-1.5"
                >
                  <span
                    className={
                      benefit.is_included
                        ? "text-slate-700"
                        : "text-slate-400 line-through"
                    }
                  >
                    {benefit.name}
                  </span>

                  <span className="text-slate-500">
                    {benefit.monetary_limit !== null
                      ? `R ${formatMoney(benefit.monetary_limit)}`
                      : benefit.quantity_limit !== null
                      ? `${benefit.quantity_limit}×`
                      : "Included"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

function PayoutPanel({ claim }: { claim: Claim }) {
  const allocations = claim.payout_allocations ?? [];

  return (
    <div className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-indigo-700">
        Payout
      </h3>

      <p className="mt-2 text-sm text-slate-600">
        Reference{" "}
        <span className="font-semibold text-slate-900">
          {claim.payment_reference}
        </span>
      </p>

      {allocations.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">
          Paid in full. No beneficiaries were recorded, so there is
          no split.
        </p>
      ) : (
        <table className="mt-3 w-full text-sm">
          <thead className="text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="py-1 text-left font-medium">
                Beneficiary
              </th>
              <th className="py-1 text-right font-medium">Share</th>
              <th className="py-1 text-right font-medium">Amount</th>
            </tr>
          </thead>

          <tbody>
            {allocations.map((allocation) => (
              <tr
                key={allocation.beneficiary_id}
                className="border-t border-indigo-100"
              >
                <td className="py-1.5 text-slate-700">
                  {allocation.name}
                  <span className="ml-2 text-xs capitalize text-slate-400">
                    {allocation.relationship}
                  </span>
                </td>

                <td className="py-1.5 text-right text-slate-500">
                  {formatPercent(allocation.share_percent)}
                </td>

                <td className="py-1.5 text-right font-semibold text-slate-900">
                  R {formatMoney(allocation.amount)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/* ============================================================
   DIALOGS
============================================================ */

function SubmitDialog({
  cases,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  cases: FuneralCase[];
  saving: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (caseId: string, amount: string, notes: string) => void;
}) {
  const [caseId, setCaseId] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit(caseId, amount, notes);
  }

  return (
    <Dialog title="Submit a claim" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field
          label="Funeral case"
          hint="Only cases linked to a membership, without a live claim, are listed."
        >
          <select
            required
            value={caseId}
            onChange={(event) => setCaseId(event.target.value)}
            className={inputClass}
          >
            <option value="">Select a case</option>

            {cases.map((item) => (
              <option key={item.id} value={item.id}>
                {item.case_number} — {item.deceased_full_name}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Amount claimed (R)">
          <input
            required
            type="number"
            inputMode="decimal"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Notes (optional)">
          <textarea
            rows={2}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className={inputClass}
          />
        </Field>

        {error && <ErrorNote message={error} />}

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel="Submit claim"
          disabled={!caseId || !amount}
        />
      </form>
    </Dialog>
  );
}

function EditDialog({
  claim,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  claim: Claim;
  saving: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (amount: string, notes: string) => void;
}) {
  const [amount, setAmount] = useState(
    String(Number(claim.claimed_amount))
  );
  const [notes, setNotes] = useState(claim.notes ?? "");

  return (
    <Dialog title={`Edit ${claim.claim_number}`} onClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(amount, notes);
        }}
        className="space-y-4"
      >
        <Field label="Amount claimed (R)">
          <input
            required
            type="number"
            inputMode="decimal"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Notes">
          <textarea
            rows={2}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className={inputClass}
          />
        </Field>

        {error && <ErrorNote message={error} />}

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel="Save changes"
        />
      </form>
    </Dialog>
  );
}

function ApproveDialog({
  claim,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  claim: Claim;
  saving: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (
    amount: string,
    note: string,
    overrideReason: string
  ) => void;
}) {
  const [amount, setAmount] = useState(
    String(Number(claim.claimed_amount))
  );
  const [note, setNote] = useState("");
  const [override, setOverride] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");

  // What the plan said when the claim was submitted. The server
  // checks again at approval, so this is a guide, not the decision.
  const snapshot = claim.submission_coverage;

  const limits = (snapshot?.benefits ?? [])
    .filter((b) => b.is_included && b.monetary_limit !== null)
    .map((b) => Number(b.monetary_limit));

  const cap = limits.length
    ? limits.reduce((sum, value) => sum + value, 0)
    : null;

  const overCap = cap !== null && Number(amount) > cap;
  const notCovered = snapshot !== null && !snapshot.covered;

  // The server refuses with a message mentioning the override when
  // it finds a problem the guide above did not predict.
  const serverWantsOverride =
    /override/i.test(error) && !/permission/i.test(error);

  const showOverride =
    override || overCap || notCovered || serverWantsOverride;

  const overrideNeeded = overCap || notCovered || serverWantsOverride;

  return (
    <Dialog title={`Approve ${claim.claim_number}`} onClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(
            amount,
            note,
            showOverride ? overrideReason : ""
          );
        }}
        className="space-y-4"
      >
        <Field
          label="Amount to approve (R)"
          hint={
            cap !== null
              ? `Claimed R ${formatMoney(
                  claim.claimed_amount
                )} · plan limit R ${formatMoney(cap)}`
              : `Claimed R ${formatMoney(claim.claimed_amount)}`
          }
        >
          <input
            required
            type="number"
            inputMode="decimal"
            min="0"
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            className={inputClass}
          />
        </Field>

        {!showOverride && (
          <Field label="Note (optional)">
            <textarea
              rows={2}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className={inputClass}
            />
          </Field>
        )}

        {notCovered && (
          <p className="flex gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            Not covered at submission: {snapshot?.reason}
          </p>
        )}

        {overCap && (
          <p className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            This is above the plan limit of R {formatMoney(cap)}.
          </p>
        )}

        {showOverride ? (
          <Field
            label="Override reason"
            hint="Approving past a cover problem needs the override permission. The reason is kept in the audit trail."
          >
            <textarea
              required
              rows={3}
              value={overrideReason}
              onChange={(event) =>
                setOverrideReason(event.target.value)
              }
              className={inputClass}
            />
          </Field>
        ) : (
          <button
            type="button"
            onClick={() => setOverride(true)}
            className="text-xs font-medium text-slate-500 underline"
          >
            Approve with an override
          </button>
        )}

        {error && <ErrorNote message={error} />}

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel={
            overrideNeeded || override
              ? "Approve with override"
              : "Approve claim"
          }
        />
      </form>
    </Dialog>
  );
}

function TextDialog({
  title,
  label,
  hint,
  required = false,
  single = false,
  submitLabel,
  danger = false,
  saving,
  error,
  footer,
  onClose,
  onSubmit,
}: {
  title: string;
  label: string;
  hint?: string;
  required?: boolean;
  single?: boolean;
  submitLabel: string;
  danger?: boolean;
  saving: boolean;
  error: string;
  footer?: React.ReactNode;
  onClose: () => void;
  onSubmit: (value: string) => void;
}) {
  const [value, setValue] = useState("");

  return (
    <Dialog title={title} onClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(value);
        }}
        className="space-y-4"
      >
        <Field label={label} hint={hint}>
          {single ? (
            <input
              required={required}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className={inputClass}
            />
          ) : (
            <textarea
              required={required}
              rows={3}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className={inputClass}
            />
          )}
        </Field>

        {footer}

        {error && <ErrorNote message={error} />}

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel={submitLabel}
          danger={danger}
          disabled={required && !value.trim()}
        />
      </form>
    </Dialog>
  );
}

/* ============================================================
   SMALL PIECES
============================================================ */

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        STATUS_STYLE[status] ?? "bg-gray-100 text-gray-600"
      }`}
    >
      {formatStatus(status)}
    </span>
  );
}

function ActionButton({
  children,
  icon,
  onClick,
  primary = false,
  danger = false,
  disabled = false,
}: {
  children: React.ReactNode;
  icon: React.ReactNode;
  onClick: () => void;
  primary?: boolean;
  danger?: boolean;
  disabled?: boolean;
}) {
  const style = primary
    ? "bg-slate-900 text-white hover:bg-slate-800"
    : danger
    ? "border border-red-200 bg-white text-red-600 hover:bg-red-50"
    : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold disabled:opacity-60 ${style}`}
    >
      {icon}
      {children}
    </button>
  );
}

function Banner({
  tone,
  children,
  onDismiss,
}: {
  tone: "error" | "success";
  children: React.ReactNode;
  onDismiss: () => void;
}) {
  const style =
    tone === "error"
      ? "border-red-200 bg-red-50 text-red-700"
      : "border-emerald-200 bg-emerald-50 text-emerald-700";

  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex items-center justify-between rounded-lg border px-4 py-3 text-sm ${style}`}
    >
      <span>{children}</span>

      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="ml-4"
      >
        <X size={18} />
      </button>
    </div>
  );
}

function ErrorNote({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      {message}
    </p>
  );
}
