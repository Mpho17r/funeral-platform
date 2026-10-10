"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  ArrowLeft,
  Ban,
  CheckCircle2,
  ChevronDown,
  FileText,
  Loader2,
  Lock,
  Pencil,
  Plus,
  Send,
  Trash2,
  X,
  XCircle,
} from "lucide-react";

import { useParams, useRouter } from "next/navigation";

import api from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

/* ============================================================
   TYPES
   Money arrives from this API as decimal strings ("7000.00"),
   so it is converted with Number() only for display.
============================================================ */

type DocumentType = "quote" | "invoice";

type DocumentLine = {
  id: string;
  document_id: string;
  position: number;
  description: string;
  quantity: string;
  unit_price: string;
  line_total: string;
  case_service_id: string | null;
};

type FinancialDocument = {
  id: string;
  case_id: string;
  document_type: DocumentType;
  number: string | null;
  status: string;
  subtotal: string;
  discount: string;
  tax: string;
  total: string;
  valid_until: string | null;
  due_date: string | null;
  source_quote_id: string | null;
  issued_at: string | null;
  accepted_at: string | null;
  voided_at: string | null;
  void_reason: string | null;
  notes: string | null;
  created_at: string;
  lines: DocumentLine[];
};

type LineForm = {
  key: string;
  description: string;
  quantity: string;
  unit_price: string;
};

type DetailsForm = {
  discount: string;
  tax: string;
  date: string;
  notes: string;
};

type Confirmation =
  | { kind: "issue"; document: FinancialDocument }
  | { kind: "delete"; document: FinancialDocument }
  | { kind: "void"; document: FinancialDocument }
  | { kind: "decline"; document: FinancialDocument }
  | null;

type Filter = "all" | DocumentType;

/* ============================================================
   API ERROR HELPER
============================================================ */

type ApiErrorShape = {
  response?: {
    status?: number;
    data?: { detail?: unknown };
  };
};

function statusOf(err: unknown): number | undefined {
  return (err as ApiErrorShape)?.response?.status;
}

function getApiErrorMessage(
  err: unknown,
  fallback: string
): string {
  const detail = (err as ApiErrorShape)?.response?.data?.detail;

  if (statusOf(err) === 403) {
    return "You do not have permission to do that.";
  }

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item: unknown) => {
        if (typeof item === "string") {
          return item;
        }

        const entry = item as { msg?: string; loc?: unknown[] };

        if (entry?.msg) {
          const location = Array.isArray(entry.loc)
            ? entry.loc.filter((part) => part !== "body").join(".")
            : "";

          return location
            ? `${location}: ${entry.msg}`
            : entry.msg;
        }

        return "Invalid request.";
      })
      .join(" ");
  }

  return fallback;
}

/* ============================================================
   MAIN PAGE
============================================================ */

export default function FinancialDocumentsPage() {
  const router = useRouter();
  const params = useParams();

  const caseId = params.case_id as string;

  const [documents, setDocuments] =
    useState<FinancialDocument[]>([]);

  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [openId, setOpenId] =
    useState<string | null>(null);

  // The error and the busy state belong to one document, so a
  // failure never appears on a different card.
  const [actionError, setActionError] = useState<{
    id: string;
    message: string;
  } | null>(null);

  const [busy, setBusy] = useState<string | null>(null);

  const [creating, setCreating] =
    useState<DocumentType | null>(null);

  const [editingDetails, setEditingDetails] =
    useState<FinancialDocument | null>(null);

  const [editingLine, setEditingLine] = useState<{
    document: FinancialDocument;
    line: DocumentLine | null;
  } | null>(null);

  const [confirmation, setConfirmation] =
    useState<Confirmation>(null);

  /* ==========================================================
     AUTH + LOAD
  ========================================================== */

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    if (!caseId) {
      return;
    }

    loadDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, router]);

  async function loadDocuments(showSpinner = true) {
    try {
      if (showSpinner) {
        setLoading(true);
      }

      setPageError("");

      const response = await api.get<FinancialDocument[]>(
        `/cases/${caseId}/financial-documents`
      );

      setDocuments(response.data);
    } catch (err) {
      if (statusOf(err) === 401) {
        router.push("/login");
        return;
      }

      setPageError(
        statusOf(err) === 403
          ? "You do not have permission to view quotes and invoices."
          : getApiErrorMessage(
              err,
              "Unable to load quotes and invoices."
            )
      );
    } finally {
      setLoading(false);
    }
  }

  /* ==========================================================
     ACTIONS
  ========================================================== */

  function replaceDocument(updated: FinancialDocument) {
    setDocuments((current) =>
      current.map((item) =>
        item.id === updated.id ? updated : item
      )
    );
  }

  async function runAction(
    document: FinancialDocument,
    key: string,
    request: () => Promise<FinancialDocument | null>,
    fallback: string
  ): Promise<boolean> {
    try {
      setBusy(`${document.id}:${key}`);
      setActionError(null);

      const result = await request();

      if (result) {
        replaceDocument(result);
      }

      return true;
    } catch (err) {
      setActionError({
        id: document.id,
        message: getApiErrorMessage(err, fallback),
      });

      return false;
    } finally {
      setBusy(null);
    }
  }

  async function handleCreate(
    type: DocumentType,
    body: Record<string, unknown>
  ) {
    const response = await api.post<FinancialDocument>(
      `/cases/${caseId}/financial-documents`,
      { ...body, document_type: type }
    );

    setDocuments((current) => [response.data, ...current]);
    setOpenId(response.data.id);
    setCreating(null);
  }

  async function handleIssue(document: FinancialDocument) {
    const ok = await runAction(
      document,
      "issue",
      async () =>
        (
          await api.post<FinancialDocument>(
            `/financial-documents/${document.id}/issue`
          )
        ).data,
      "Unable to issue this document."
    );

    if (ok) {
      setConfirmation(null);
    }
  }

  async function handleQuoteDecision(
    document: FinancialDocument,
    decision: "accept" | "decline"
  ) {
    const ok = await runAction(
      document,
      decision,
      async () =>
        (
          await api.post<FinancialDocument>(
            `/financial-documents/${document.id}/${decision}`
          )
        ).data,
      `Unable to ${decision} this quote.`
    );

    if (ok) {
      setConfirmation(null);
    }
  }

  async function handleConvert(document: FinancialDocument) {
    const ok = await runAction(
      document,
      "convert",
      async () => {
        const response = await api.post<FinancialDocument>(
          `/financial-documents/${document.id}/convert`
        );

        await loadDocuments(false);
        setOpenId(response.data.id);

        return null;
      },
      "Unable to convert this quote."
    );

    return ok;
  }

  async function handleVoid(
    document: FinancialDocument,
    reason: string
  ) {
    return runAction(
      document,
      "void",
      async () =>
        (
          await api.post<FinancialDocument>(
            `/financial-documents/${document.id}/void`,
            { reason }
          )
        ).data,
      "Unable to void this document."
    );
  }

  async function handleDelete(document: FinancialDocument) {
    const ok = await runAction(
      document,
      "delete",
      async () => {
        await api.delete(
          `/financial-documents/${document.id}`
        );

        setDocuments((current) =>
          current.filter((item) => item.id !== document.id)
        );

        return null;
      },
      "Unable to delete this draft."
    );

    if (ok) {
      setConfirmation(null);
      setOpenId(null);
    }
  }

  async function handleRemoveLine(
    document: FinancialDocument,
    line: DocumentLine
  ) {
    await runAction(
      document,
      `line:${line.id}`,
      async () =>
        (
          await api.delete<FinancialDocument>(
            `/financial-documents/${document.id}/lines/${line.id}`
          )
        ).data,
      "Unable to remove this line."
    );
  }

  /* ==========================================================
     DERIVED
  ========================================================== */

  const visible = documents.filter(
    (item) =>
      filter === "all" || item.document_type === filter
  );

  const quoteNumbers = new Map(
    documents.map((item) => [item.id, item.number])
  );

  /* ==========================================================
     LOADING
  ========================================================== */

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <Loader2 size={20} className="animate-spin" />
          Loading quotes and invoices...
        </div>
      </main>
    );
  }

  /* ==========================================================
     PAGE
  ========================================================== */

  return (
    <main className="min-h-screen bg-slate-100">
      <header className="border-b bg-white">
        <div className="mx-auto max-w-7xl px-6 py-5 md:px-8">
          <button
            onClick={() =>
              router.push(`/cases/${caseId}/financial`)
            }
            className="mb-5 flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900"
          >
            <ArrowLeft size={17} />
            Back to Case Financials
          </button>

          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-slate-100 p-3 text-slate-700">
                <FileText size={24} />
              </div>

              <div>
                <h1 className="text-2xl font-bold text-slate-900">
                  Quotes &amp; Invoices
                </h1>

                <p className="mt-1 text-sm text-slate-500">
                  Draft, issue and track the documents
                  for this case. Issued documents are
                  permanent.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => setCreating("quote")}
                className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                <Plus size={16} />
                New Quote
              </button>

              <button
                onClick={() => setCreating("invoice")}
                className="flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
              >
                <Plus size={16} />
                New Invoice
              </button>
            </div>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl space-y-6 p-6 md:p-8">
        {pageError && <ErrorBox>{pageError}</ErrorBox>}

        {/* FILTER */}
        <div
          className="flex gap-2"
          role="tablist"
          aria-label="Document type"
        >
          {(
            [
              ["all", "All"],
              ["quote", "Quotes"],
              ["invoice", "Invoices"],
            ] as [Filter, string][]
          ).map(([value, label]) => (
            <button
              key={value}
              role="tab"
              aria-selected={filter === value}
              onClick={() => setFilter(value)}
              className={`rounded-full px-4 py-2 text-sm font-medium ${
                filter === value
                  ? "bg-slate-900 text-white"
                  : "bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* EMPTY */}
        {visible.length === 0 && !pageError && (
          <div className="rounded-2xl border bg-white p-10 text-center shadow-sm">
            <FileText
              size={32}
              className="mx-auto text-slate-400"
            />

            <h2 className="mt-3 font-semibold text-slate-800">
              {documents.length === 0
                ? "No quotes or invoices yet"
                : "Nothing matches this filter"}
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              {documents.length === 0
                ? "Start with a quote for the family, then turn it into an invoice once it is accepted."
                : "Try another filter."}
            </p>
          </div>
        )}

        {/* LIST */}
        <div className="space-y-4">
          {visible.map((document) => (
            <DocumentCard
              key={document.id}
              document={document}
              open={openId === document.id}
              onToggle={() =>
                setOpenId(
                  openId === document.id ? null : document.id
                )
              }
              busy={busy}
              error={
                actionError?.id === document.id
                  ? actionError.message
                  : ""
              }
              sourceNumber={
                document.source_quote_id
                  ? quoteNumbers.get(document.source_quote_id) ??
                    null
                  : null
              }
              onEditDetails={() => setEditingDetails(document)}
              onAddLine={() =>
                setEditingLine({ document, line: null })
              }
              onEditLine={(line) =>
                setEditingLine({ document, line })
              }
              onRemoveLine={(line) =>
                handleRemoveLine(document, line)
              }
              onConfirm={(kind) =>
                setConfirmation({ kind, document })
              }
              onAccept={() =>
                handleQuoteDecision(document, "accept")
              }
              onConvert={() => handleConvert(document)}
            />
          ))}
        </div>
      </section>

      {/* ======================================================
          DIALOGS
      ====================================================== */}

      {creating && (
        <CreateDialog
          type={creating}
          onClose={() => setCreating(null)}
          onCreate={handleCreate}
        />
      )}

      {editingDetails && (
        <DetailsDialog
          document={editingDetails}
          onClose={() => setEditingDetails(null)}
          onSaved={(updated) => {
            replaceDocument(updated);
            setEditingDetails(null);
          }}
        />
      )}

      {editingLine && (
        <LineDialog
          document={editingLine.document}
          line={editingLine.line}
          onClose={() => setEditingLine(null)}
          onSaved={(updated) => {
            replaceDocument(updated);
            setEditingLine(null);
          }}
        />
      )}

      {confirmation?.kind === "issue" && (
        <ConfirmDialog
          title={`Issue this ${confirmation.document.document_type}?`}
          confirmLabel="Issue"
          busy={
            busy === `${confirmation.document.id}:issue`
          }
          error={
            actionError?.id === confirmation.document.id
              ? actionError.message
              : ""
          }
          onCancel={() => {
            setConfirmation(null);
            setActionError(null);
          }}
          onConfirm={() => handleIssue(confirmation.document)}
        >
          It will be given its number and can no longer be
          edited or deleted. If something is wrong later it
          can only be voided with a reason.
        </ConfirmDialog>
      )}

      {confirmation?.kind === "decline" && (
        <ConfirmDialog
          title="Decline this quote?"
          confirmLabel="Decline quote"
          danger
          busy={
            busy === `${confirmation.document.id}:decline`
          }
          error={
            actionError?.id === confirmation.document.id
              ? actionError.message
              : ""
          }
          onCancel={() => {
            setConfirmation(null);
            setActionError(null);
          }}
          onConfirm={() =>
            handleQuoteDecision(confirmation.document, "decline")
          }
        >
          A declined quote is final. You can still create a new
          quote for the family.
        </ConfirmDialog>
      )}

      {confirmation?.kind === "delete" && (
        <ConfirmDialog
          title="Delete this draft?"
          confirmLabel="Delete draft"
          danger
          busy={
            busy === `${confirmation.document.id}:delete`
          }
          error={
            actionError?.id === confirmation.document.id
              ? actionError.message
              : ""
          }
          onCancel={() => {
            setConfirmation(null);
            setActionError(null);
          }}
          onConfirm={() => handleDelete(confirmation.document)}
        >
          Drafts have no number, so deleting one leaves no gap
          in your numbering.
        </ConfirmDialog>
      )}

      {confirmation?.kind === "void" && (
        <VoidDialog
          document={confirmation.document}
          busy={busy === `${confirmation.document.id}:void`}
          error={
            actionError?.id === confirmation.document.id
              ? actionError.message
              : ""
          }
          onCancel={() => {
            setConfirmation(null);
            setActionError(null);
          }}
          onVoid={async (reason) => {
            const ok = await handleVoid(
              confirmation.document,
              reason
            );

            if (ok) {
              setConfirmation(null);
            }
          }}
        />
      )}
    </main>
  );
}

/* ============================================================
   DOCUMENT CARD
============================================================ */

function DocumentCard({
  document,
  open,
  onToggle,
  busy,
  error,
  sourceNumber,
  onEditDetails,
  onAddLine,
  onEditLine,
  onRemoveLine,
  onConfirm,
  onAccept,
  onConvert,
}: {
  document: FinancialDocument;
  open: boolean;
  onToggle: () => void;
  busy: string | null;
  error: string;
  sourceNumber: string | null;
  onEditDetails: () => void;
  onAddLine: () => void;
  onEditLine: (line: DocumentLine) => void;
  onRemoveLine: (line: DocumentLine) => void;
  onConfirm: (
    kind: "issue" | "delete" | "void" | "decline"
  ) => void;
  onAccept: () => void;
  onConvert: () => void;
}) {
  const isDraft = document.status === "draft";
  const isQuote = document.document_type === "quote";

  const canVoid =
    (isQuote &&
      ["issued", "accepted"].includes(document.status)) ||
    (!isQuote && document.status === "issued");

  const working = (key: string) =>
    busy === `${document.id}:${key}`;

  const anyBusy = busy?.startsWith(`${document.id}:`) ?? false;

  const dateLabel = isQuote ? "Valid until" : "Due";
  const dateValue = isQuote
    ? document.valid_until
    : document.due_date;

  return (
    <article className="rounded-2xl border bg-white shadow-sm">
      <button
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full flex-col gap-3 p-5 text-left md:flex-row md:items-center md:justify-between"
      >
        <div className="flex items-center gap-4">
          <div
            className={`rounded-lg p-2 ${
              isQuote
                ? "bg-sky-50 text-sky-700"
                : "bg-indigo-50 text-indigo-700"
            }`}
          >
            <FileText size={20} />
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold text-slate-900">
                {document.number ??
                  `Draft ${isQuote ? "quote" : "invoice"}`}
              </h2>

              <StatusBadge status={document.status} />
            </div>

            <p className="mt-1 text-xs text-slate-500">
              {isQuote ? "Quote" : "Invoice"}
              {dateValue &&
                ` · ${dateLabel} ${formatDate(dateValue)}`}
              {sourceNumber &&
                ` · From quote ${sourceNumber}`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <p className="text-lg font-bold text-slate-900">
            R {formatMoney(document.total)}
          </p>

          <ChevronDown
            size={18}
            className={`text-slate-400 transition-transform ${
              open ? "rotate-180" : ""
            }`}
          />
        </div>
      </button>

      {open && (
        <div className="space-y-5 border-t p-5">
          {error && <ErrorBox>{error}</ErrorBox>}

          {!isDraft && (
            <div className="flex items-center gap-2 rounded-lg bg-slate-50 px-4 py-3 text-xs text-slate-600">
              <Lock size={14} />
              {document.status === "void"
                ? "This document was voided and is kept on record."
                : "Issued documents are permanent. They can only be voided."}
            </div>
          )}

          {document.status === "void" && document.void_reason && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              <span className="font-semibold">
                Void reason:
              </span>{" "}
              {document.void_reason}
            </div>
          )}

          {/* LINES */}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-slate-400">
                  <th className="pb-2 font-medium">
                    Description
                  </th>
                  <th className="pb-2 text-right font-medium">
                    Qty
                  </th>
                  <th className="pb-2 text-right font-medium">
                    Unit price
                  </th>
                  <th className="pb-2 text-right font-medium">
                    Total
                  </th>
                  {isDraft && (
                    <th className="w-20 pb-2">
                      <span className="sr-only">Actions</span>
                    </th>
                  )}
                </tr>
              </thead>

              <tbody>
                {document.lines.length === 0 && (
                  <tr>
                    <td
                      colSpan={isDraft ? 5 : 4}
                      className="py-6 text-center text-slate-500"
                    >
                      No lines yet. Add at least one before
                      issuing.
                    </td>
                  </tr>
                )}

                {document.lines.map((line) => (
                  <tr key={line.id} className="border-b last:border-0">
                    <td className="py-3 text-slate-800">
                      {line.description}
                    </td>
                    <td className="py-3 text-right text-slate-600">
                      {formatQuantity(line.quantity)}
                    </td>
                    <td className="py-3 text-right text-slate-600">
                      R {formatMoney(line.unit_price)}
                    </td>
                    <td className="py-3 text-right font-medium text-slate-900">
                      R {formatMoney(line.line_total)}
                    </td>
                    {isDraft && (
                      <td className="py-3">
                        <div className="flex justify-end gap-1">
                          <button
                            onClick={() => onEditLine(line)}
                            aria-label={`Edit ${line.description}`}
                            className="rounded p-1.5 text-slate-500 hover:bg-slate-100"
                          >
                            <Pencil size={15} />
                          </button>

                          <button
                            onClick={() => onRemoveLine(line)}
                            disabled={anyBusy}
                            aria-label={`Remove ${line.description}`}
                            className="rounded p-1.5 text-slate-500 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                          >
                            {working(`line:${line.id}`) ? (
                              <Loader2
                                size={15}
                                className="animate-spin"
                              />
                            ) : (
                              <Trash2 size={15} />
                            )}
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {isDraft && (
            <button
              onClick={onAddLine}
              className="flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-slate-900"
            >
              <Plus size={16} />
              Add line
            </button>
          )}

          {/* TOTALS */}
          <dl className="ml-auto w-full max-w-xs space-y-2 text-sm">
            <TotalRow label="Subtotal" value={document.subtotal} />
            <TotalRow
              label="Discount"
              value={document.discount}
              negative
            />
            <TotalRow label="Tax" value={document.tax} />
            <div className="flex justify-between border-t pt-2 text-base font-bold text-slate-900">
              <dt>Total</dt>
              <dd>R {formatMoney(document.total)}</dd>
            </div>
          </dl>

          {document.notes && (
            <p className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600">
              {document.notes}
            </p>
          )}

          {/* META */}
          <p className="text-xs text-slate-400">
            Created {formatDate(document.created_at)}
            {document.issued_at &&
              ` · Issued ${formatDate(document.issued_at)}`}
            {document.accepted_at &&
              ` · Accepted ${formatDate(document.accepted_at)}`}
            {document.voided_at &&
              ` · Voided ${formatDate(document.voided_at)}`}
          </p>

          {/* ACTIONS */}
          <div className="flex flex-wrap gap-3 border-t pt-4">
            {isDraft && (
              <>
                <ActionButton
                  primary
                  onClick={() => onConfirm("issue")}
                  disabled={
                    anyBusy || document.lines.length === 0
                  }
                  icon={<Send size={16} />}
                  title={
                    document.lines.length === 0
                      ? "Add a line before issuing"
                      : undefined
                  }
                >
                  Issue
                </ActionButton>

                <ActionButton
                  onClick={onEditDetails}
                  disabled={anyBusy}
                  icon={<Pencil size={16} />}
                >
                  Edit details
                </ActionButton>

                <ActionButton
                  danger
                  onClick={() => onConfirm("delete")}
                  disabled={anyBusy}
                  icon={<Trash2 size={16} />}
                >
                  Delete draft
                </ActionButton>
              </>
            )}

            {isQuote && document.status === "issued" && (
              <>
                <ActionButton
                  primary
                  onClick={onAccept}
                  disabled={anyBusy}
                  busy={working("accept")}
                  icon={<CheckCircle2 size={16} />}
                >
                  Mark accepted
                </ActionButton>

                <ActionButton
                  onClick={() => onConfirm("decline")}
                  disabled={anyBusy}
                  icon={<XCircle size={16} />}
                >
                  Mark declined
                </ActionButton>
              </>
            )}

            {isQuote && document.status === "accepted" && (
              <ActionButton
                primary
                onClick={onConvert}
                disabled={anyBusy}
                busy={working("convert")}
                icon={<FileText size={16} />}
              >
                Convert to invoice
              </ActionButton>
            )}

            {canVoid && (
              <ActionButton
                danger
                onClick={() => onConfirm("void")}
                disabled={anyBusy}
                icon={<Ban size={16} />}
              >
                Void
              </ActionButton>
            )}
          </div>
        </div>
      )}
    </article>
  );
}

/* ============================================================
   DIALOGS
============================================================ */

function CreateDialog({
  type,
  onClose,
  onCreate,
}: {
  type: DocumentType;
  onClose: () => void;
  onCreate: (
    type: DocumentType,
    body: Record<string, unknown>
  ) => Promise<void>;
}) {
  const [lines, setLines] = useState<LineForm[]>([newLine()]);
  const [discount, setDiscount] = useState("0.00");
  const [tax, setTax] = useState("0.00");
  const [date, setDate] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const isQuote = type === "quote";

  function updateLine(key: string, patch: Partial<LineForm>) {
    setLines((current) =>
      current.map((line) =>
        line.key === key ? { ...line, ...patch } : line
      )
    );
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    const filled = lines.filter(
      (line) => line.description.trim() !== ""
    );

    if (filled.length === 0) {
      setError("Add at least one line with a description.");
      return;
    }

    try {
      setSaving(true);
      setError("");

      await onCreate(type, {
        discount: discount || "0",
        tax: tax || "0",
        valid_until: isQuote && date ? date : null,
        due_date: !isQuote && date ? date : null,
        notes: notes.trim() || null,
        lines: filled.map((line) => ({
          description: line.description.trim(),
          quantity: line.quantity || "1",
          unit_price: line.unit_price || "0",
        })),
      });
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Unable to create the draft.")
      );
      setSaving(false);
    }
  }

  return (
    <Dialog
      title={`New ${isQuote ? "quote" : "invoice"}`}
      onClose={onClose}
      wide
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {error && <ErrorBox>{error}</ErrorBox>}

        <fieldset className="space-y-3">
          <legend className="mb-1 text-sm font-medium text-slate-700">
            Lines
          </legend>

          {lines.map((line, index) => (
            <div
              key={line.key}
              className="grid grid-cols-12 items-end gap-2"
            >
              <div className="col-span-12 md:col-span-6">
                <TextField
                  label={index === 0 ? "Description" : ""}
                  ariaLabel={`Line ${index + 1} description`}
                  value={line.description}
                  onChange={(value) =>
                    updateLine(line.key, { description: value })
                  }
                  placeholder="e.g. Standard coffin"
                />
              </div>

              <div className="col-span-4 md:col-span-2">
                <NumberField
                  label={index === 0 ? "Qty" : ""}
                  ariaLabel={`Line ${index + 1} quantity`}
                  value={line.quantity}
                  min="0.01"
                  onChange={(value) =>
                    updateLine(line.key, { quantity: value })
                  }
                />
              </div>

              <div className="col-span-6 md:col-span-3">
                <NumberField
                  label={index === 0 ? "Unit price (R)" : ""}
                  ariaLabel={`Line ${index + 1} unit price`}
                  value={line.unit_price}
                  onChange={(value) =>
                    updateLine(line.key, { unit_price: value })
                  }
                />
              </div>

              <div className="col-span-2 md:col-span-1">
                <button
                  type="button"
                  onClick={() =>
                    setLines((current) =>
                      current.length === 1
                        ? current
                        : current.filter(
                            (item) => item.key !== line.key
                          )
                    )
                  }
                  disabled={lines.length === 1}
                  aria-label={`Remove line ${index + 1}`}
                  className="rounded p-2.5 text-slate-500 hover:bg-red-50 hover:text-red-600 disabled:opacity-30"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}

          <button
            type="button"
            onClick={() =>
              setLines((current) => [...current, newLine()])
            }
            className="flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-slate-900"
          >
            <Plus size={16} />
            Add another line
          </button>
        </fieldset>

        <div className="grid gap-4 md:grid-cols-3">
          <NumberField
            label="Discount (R)"
            value={discount}
            onChange={setDiscount}
          />

          <NumberField
            label="Tax (R)"
            value={tax}
            onChange={setTax}
          />

          <DateField
            label={
              isQuote
                ? "Valid until (default 30 days)"
                : "Due date (default 14 days)"
            }
            value={date}
            onChange={setDate}
          />
        </div>

        <TextField
          label="Notes"
          value={notes}
          onChange={setNotes}
          placeholder="Optional"
        />

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel="Create draft"
        />
      </form>
    </Dialog>
  );
}

function DetailsDialog({
  document,
  onClose,
  onSaved,
}: {
  document: FinancialDocument;
  onClose: () => void;
  onSaved: (updated: FinancialDocument) => void;
}) {
  const isQuote = document.document_type === "quote";

  const [form, setForm] = useState<DetailsForm>({
    discount: document.discount,
    tax: document.tax,
    date:
      (isQuote ? document.valid_until : document.due_date) ?? "",
    notes: document.notes ?? "",
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    try {
      setSaving(true);
      setError("");

      const response = await api.patch<FinancialDocument>(
        `/financial-documents/${document.id}`,
        {
          discount: form.discount || "0",
          tax: form.tax || "0",
          [isQuote ? "valid_until" : "due_date"]:
            form.date || null,
          notes: form.notes.trim() || null,
        }
      );

      onSaved(response.data);
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Unable to save the changes.")
      );
      setSaving(false);
    }
  }

  return (
    <Dialog title="Edit details" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <ErrorBox>{error}</ErrorBox>}

        <div className="grid gap-4 md:grid-cols-2">
          <NumberField
            label="Discount (R)"
            value={form.discount}
            onChange={(value) =>
              setForm({ ...form, discount: value })
            }
          />

          <NumberField
            label="Tax (R)"
            value={form.tax}
            onChange={(value) =>
              setForm({ ...form, tax: value })
            }
          />
        </div>

        <DateField
          label={isQuote ? "Valid until" : "Due date"}
          value={form.date}
          onChange={(value) =>
            setForm({ ...form, date: value })
          }
        />

        <TextField
          label="Notes"
          value={form.notes}
          onChange={(value) =>
            setForm({ ...form, notes: value })
          }
        />

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel="Save changes"
        />
      </form>
    </Dialog>
  );
}

function LineDialog({
  document,
  line,
  onClose,
  onSaved,
}: {
  document: FinancialDocument;
  line: DocumentLine | null;
  onClose: () => void;
  onSaved: (updated: FinancialDocument) => void;
}) {
  const [description, setDescription] = useState(
    line?.description ?? ""
  );
  const [quantity, setQuantity] = useState(
    line?.quantity ?? "1"
  );
  const [unitPrice, setUnitPrice] = useState(
    line?.unit_price ?? "0.00"
  );

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (!description.trim()) {
      setError("Enter a description.");
      return;
    }

    const body = {
      description: description.trim(),
      quantity: quantity || "1",
      unit_price: unitPrice || "0",
    };

    try {
      setSaving(true);
      setError("");

      const response = line
        ? await api.patch<FinancialDocument>(
            `/financial-documents/${document.id}/lines/${line.id}`,
            body
          )
        : await api.post<FinancialDocument>(
            `/financial-documents/${document.id}/lines`,
            body
          );

      onSaved(response.data);
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Unable to save this line.")
      );
      setSaving(false);
    }
  }

  return (
    <Dialog
      title={line ? "Edit line" : "Add line"}
      onClose={onClose}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <ErrorBox>{error}</ErrorBox>}

        <TextField
          label="Description"
          value={description}
          onChange={setDescription}
          autoFocus
        />

        <div className="grid gap-4 md:grid-cols-2">
          <NumberField
            label="Quantity"
            value={quantity}
            min="0.01"
            onChange={setQuantity}
          />

          <NumberField
            label="Unit price (R)"
            value={unitPrice}
            onChange={setUnitPrice}
          />
        </div>

        <DialogFooter
          onClose={onClose}
          saving={saving}
          submitLabel={line ? "Save line" : "Add line"}
        />
      </form>
    </Dialog>
  );
}

function VoidDialog({
  document,
  busy,
  error,
  onCancel,
  onVoid,
}: {
  document: FinancialDocument;
  busy: boolean;
  error: string;
  onCancel: () => void;
  onVoid: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");

  return (
    <Dialog
      title={`Void ${document.number ?? "document"}?`}
      onClose={onCancel}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();

          if (reason.trim()) {
            onVoid(reason.trim());
          }
        }}
        className="space-y-4"
      >
        {error && <ErrorBox>{error}</ErrorBox>}

        <p className="text-sm text-slate-600">
          The document stays on record with its number. This
          cannot be undone, and a reason is required.
        </p>

        <TextField
          label="Reason"
          value={reason}
          onChange={setReason}
          autoFocus
          required
        />

        <DialogFooter
          onClose={onCancel}
          saving={busy}
          submitLabel="Void document"
          danger
          disabled={!reason.trim()}
        />
      </form>
    </Dialog>
  );
}

function ConfirmDialog({
  title,
  children,
  confirmLabel,
  danger = false,
  busy,
  error,
  onCancel,
  onConfirm,
}: {
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  danger?: boolean;
  busy: boolean;
  error: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog title={title} onClose={onCancel}>
      <div className="space-y-4">
        {error && <ErrorBox>{error}</ErrorBox>}

        <p className="text-sm text-slate-600">{children}</p>

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60 ${
              danger
                ? "bg-red-600 hover:bg-red-700"
                : "bg-slate-900 hover:bg-slate-800"
            }`}
          >
            {busy && (
              <Loader2 size={16} className="animate-spin" />
            )}
            {confirmLabel}
          </button>
        </div>
      </div>
    </Dialog>
  );
}

/* ============================================================
   SHARED COMPONENTS
============================================================ */

function Dialog({
  title,
  onClose,
  wide = false,
  children,
}: {
  title: string;
  onClose: () => void;
  wide?: boolean;
  children: React.ReactNode;
}) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", onKey);

    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 md:items-center"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`w-full rounded-2xl bg-white p-6 shadow-xl ${
          wide ? "max-w-3xl" : "max-w-lg"
        }`}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">
            {title}
          </h2>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1.5 text-slate-500 hover:bg-slate-100"
          >
            <X size={18} />
          </button>
        </div>

        {children}
      </div>
    </div>
  );
}

function DialogFooter({
  onClose,
  saving,
  submitLabel,
  danger = false,
  disabled = false,
}: {
  onClose: () => void;
  saving: boolean;
  submitLabel: string;
  danger?: boolean;
  disabled?: boolean;
}) {
  return (
    <div className="flex justify-end gap-3 pt-2">
      <button
        type="button"
        onClick={onClose}
        className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        Cancel
      </button>

      <button
        type="submit"
        disabled={saving || disabled}
        className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60 ${
          danger
            ? "bg-red-600 hover:bg-red-700"
            : "bg-slate-900 hover:bg-slate-800"
        }`}
      >
        {saving && (
          <Loader2 size={16} className="animate-spin" />
        )}
        {submitLabel}
      </button>
    </div>
  );
}

function ErrorBox({ children }: { children: string }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      {children}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    draft: "bg-slate-100 text-slate-700",
    issued: "bg-sky-50 text-sky-700",
    accepted: "bg-emerald-50 text-emerald-700",
    declined: "bg-amber-50 text-amber-700",
    converted: "bg-indigo-50 text-indigo-700",
    void: "bg-red-50 text-red-700",
  };

  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-semibold ${
        styles[status] || "bg-slate-100 text-slate-700"
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
  disabled,
  busy = false,
  primary = false,
  danger = false,
  title,
}: {
  children: React.ReactNode;
  icon: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  primary?: boolean;
  danger?: boolean;
  title?: string;
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
      title={title}
      className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${style}`}
    >
      {busy ? (
        <Loader2 size={16} className="animate-spin" />
      ) : (
        icon
      )}
      {children}
    </button>
  );
}

function TotalRow({
  label,
  value,
  negative = false,
}: {
  label: string;
  value: string;
  negative?: boolean;
}) {
  return (
    <div className="flex justify-between text-slate-600">
      <dt>{label}</dt>
      <dd>
        {negative && Number(value) > 0 ? "− " : ""}R{" "}
        {formatMoney(value)}
      </dd>
    </div>
  );
}

const inputClass =
  "w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200";

function TextField({
  label,
  value,
  onChange,
  placeholder,
  ariaLabel,
  autoFocus = false,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  ariaLabel?: string;
  autoFocus?: boolean;
  required?: boolean;
}) {
  return (
    <label className="block">
      {label && (
        <span className="mb-2 block text-sm font-medium text-slate-700">
          {label}
        </span>
      )}

      <input
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={ariaLabel}
        autoFocus={autoFocus}
        required={required}
        className={inputClass}
      />
    </label>
  );
}

function NumberField({
  label,
  value,
  onChange,
  ariaLabel,
  min = "0",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  ariaLabel?: string;
  min?: string;
}) {
  return (
    <label className="block">
      {label && (
        <span className="mb-2 block text-sm font-medium text-slate-700">
          {label}
        </span>
      )}

      <input
        type="number"
        inputMode="decimal"
        min={min}
        step="0.01"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={ariaLabel}
        className={inputClass}
      />
    </label>
  );
}

function DateField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </span>

      <input
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={inputClass}
      />
    </label>
  );
}

/* ============================================================
   HELPERS
============================================================ */

function newLine(): LineForm {
  return {
    key: Math.random().toString(36).slice(2),
    description: "",
    quantity: "1",
    unit_price: "",
  };
}

function formatMoney(value: string | number) {
  return Number(value || 0).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatQuantity(value: string) {
  return Number(value).toLocaleString("en-ZA", {
    maximumFractionDigits: 2,
  });
}

function formatDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatStatus(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
