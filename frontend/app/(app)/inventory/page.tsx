"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpFromLine,
  Boxes,
  Loader2,
  MoreHorizontal,
  Plus,
  Search,
} from "lucide-react";

import api from "@/lib/api";
import { useBranches } from "@/lib/branches";
import { formatMoney, getApiErrorMessage, statusOf } from "@/lib/format";
import { formatDateTime } from "@/lib/datetime";
import {
  CATEGORIES,
  MOVEMENT_LABELS,
  categoryLabel,
  formatQty,
  formatSignedQty,
} from "@/lib/inventory";
import type {
  InventoryItem,
  StockMovement,
  Supplier,
} from "@/lib/inventory";
import {
  ALL_BRANCHES,
  BranchBadge,
  BranchFilter,
  BranchSelect,
  TransferDialog,
  matchesBranch,
} from "@/components/BranchControls";
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

type CaseOption = {
  id: string;
  case_number: string;
  deceased_full_name: string;
};

type StockMode = "receipt" | "issue" | "return";

type Dialogue =
  | { kind: "create" }
  | { kind: "edit"; item: InventoryItem }
  | { kind: "stock"; item: InventoryItem; mode: StockMode }
  | { kind: "adjust"; item: InventoryItem }
  | { kind: "detail"; item: InventoryItem }
  | { kind: "move"; item: InventoryItem }
  | { kind: "deactivate"; item: InventoryItem }
  | null;

type ItemForm = {
  sku: string;
  name: string;
  category: string;
  unit: string;
  supplier_id: string;
  reorder_level: string;
  unit_cost: string;
  opening_quantity: string;
  description: string;
  branch_id: string;
};

const emptyItemForm: ItemForm = {
  sku: "",
  name: "",
  category: "coffin",
  unit: "each",
  supplier_id: "",
  reorder_level: "0",
  unit_cost: "",
  opening_quantity: "0",
  description: "",
  branch_id: "",
};

const STOCK_TITLES: Record<StockMode, string> = {
  receipt: "Receive stock",
  issue: "Issue stock",
  return: "Return stock",
};

/* ============================================================
   PAGE
============================================================ */

export default function InventoryPage() {
  const branchData = useBranches();

  const [items, setItems] = useState<InventoryItem[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [cases, setCases] = useState<CaseOption[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [lowOnly, setLowOnly] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  const [branchFilter, setBranchFilter] = useState(ALL_BRANCHES);

  const [dialog, setDialog] = useState<Dialogue>(null);
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  const [itemForm, setItemForm] = useState<ItemForm>(emptyItemForm);

  const [stockForm, setStockForm] = useState({
    quantity: "",
    unit_cost: "",
    supplier_id: "",
    case_id: "",
    reference: "",
    reason: "",
  });

  const [adjustForm, setAdjustForm] = useState({
    direction: "remove",
    quantity: "",
    reason: "",
  });

  const [history, setHistory] = useState<StockMovement[] | null>(null);

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await api.get<InventoryItem[]>(
          "/inventory/items",
          { params: { include_inactive: true } }
        );

        if (!cancelled) {
          setItems(response.data);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            statusOf(err) === 401
              ? "Your session has expired. Please log in again."
              : getApiErrorMessage(err, "Failed to load inventory.")
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }

      // Suppliers and cases only fill dropdowns. The page still works
      // without them.
      const [supplierResult, caseResult] = await Promise.allSettled([
        api.get<Supplier[]>("/suppliers", {
          params: { include_inactive: true },
        }),
        api.get<CaseOption[]>("/cases"),
      ]);

      if (cancelled) {
        return;
      }

      if (supplierResult.status === "fulfilled") {
        setSuppliers(supplierResult.value.data);
      }

      if (caseResult.status === "fulfilled") {
        setCases(caseResult.value.data);
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  // The ledger of the item whose detail is open.
  const detailId =
    dialog?.kind === "detail" ? dialog.item.id : null;

  useEffect(() => {
    if (!detailId) {
      return;
    }

    let cancelled = false;

    api
      .get<StockMovement[]>(`/inventory/items/${detailId}/movements`)
      .then((response) => {
        if (!cancelled) {
          setHistory(response.data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHistory([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [detailId, reloadKey]);

  const supplierById = useMemo(
    () => new Map(suppliers.map((s) => [s.id, s])),
    [suppliers]
  );

  const caseById = useMemo(
    () => new Map(cases.map((c) => [c.id, c])),
    [cases]
  );

  function reload() {
    setReloadKey((current) => current + 1);
  }

  function closeDialog() {
    setDialog(null);
    setDialogError("");
    setHistory(null);
  }

  /** Run a change; on success close, tell the user and refetch. */
  async function run(
    action: () => Promise<unknown>,
    success: string,
    fallback: string
  ) {
    setSaving(true);
    setDialogError("");

    try {
      await action();

      closeDialog();
      setNotice(success);
      reload();
    } catch (err) {
      setDialogError(getApiErrorMessage(err, fallback));
    } finally {
      setSaving(false);
    }
  }

  /* ---------------- item dialogs ---------------- */

  function openCreate() {
    setItemForm(emptyItemForm);
    setDialogError("");
    setDialog({ kind: "create" });
  }

  function openEdit(item: InventoryItem) {
    setItemForm({
      sku: item.sku,
      name: item.name,
      category: item.category,
      unit: item.unit,
      supplier_id: item.supplier_id ?? "",
      reorder_level: String(Number(item.reorder_level)),
      unit_cost: item.unit_cost ?? "",
      opening_quantity: "0",
      description: item.description ?? "",
      branch_id: "",
    });
    setDialogError("");
    setDialog({ kind: "edit", item });
  }

  function handleItemSubmit(event: FormEvent) {
    event.preventDefault();

    const shared = {
      name: itemForm.name.trim(),
      category: itemForm.category,
      unit: itemForm.unit.trim() || "each",
      description: itemForm.description.trim() || null,
      supplier_id: itemForm.supplier_id || null,
      reorder_level: itemForm.reorder_level || "0",
      unit_cost: itemForm.unit_cost.trim() || null,
    };

    if (dialog?.kind === "edit") {
      run(
        () => api.patch(`/inventory/items/${dialog.item.id}`, shared),
        `${shared.name} was updated.`,
        "Could not save the item."
      );

      return;
    }

    run(
      () =>
        api.post("/inventory/items", {
          ...shared,
          sku: itemForm.sku.trim(),
          opening_quantity: itemForm.opening_quantity || "0",
          // Left empty, the server uses the creator's own branch.
          ...(itemForm.branch_id
            ? { branch_id: itemForm.branch_id }
            : {}),
        }),
      `${shared.name} was added.`,
      "Could not add the item."
    );
  }

  /* ---------------- stock dialogs ---------------- */

  function openStock(item: InventoryItem, mode: StockMode) {
    setStockForm({
      quantity: "",
      unit_cost: mode === "receipt" ? item.unit_cost ?? "" : "",
      supplier_id: mode === "receipt" ? item.supplier_id ?? "" : "",
      case_id: "",
      reference: "",
      reason: "",
    });
    setDialogError("");
    setDialog({ kind: "stock", item, mode });
  }

  function handleStockSubmit(event: FormEvent) {
    event.preventDefault();

    if (dialog?.kind !== "stock") {
      return;
    }

    const { item, mode } = dialog;

    const body: Record<string, string> = {
      movement_type: mode,
      quantity: stockForm.quantity,
    };

    if (mode === "receipt") {
      if (stockForm.unit_cost.trim()) {
        body.unit_cost = stockForm.unit_cost.trim();
      }

      if (stockForm.supplier_id) {
        body.supplier_id = stockForm.supplier_id;
      }
    } else if (stockForm.case_id) {
      body.case_id = stockForm.case_id;
    }

    if (stockForm.reference.trim()) {
      body.reference = stockForm.reference.trim();
    }

    if (stockForm.reason.trim()) {
      body.reason = stockForm.reason.trim();
    }

    const verb = {
      receipt: "received",
      issue: "issued",
      return: "returned",
    }[mode];

    run(
      () => api.post(`/inventory/items/${item.id}/movements`, body),
      `${formatQty(stockForm.quantity)} ${item.unit} of ${
        item.name
      } ${verb}.`,
      "Could not record the stock change."
    );
  }

  function openAdjust(item: InventoryItem) {
    setAdjustForm({ direction: "remove", quantity: "", reason: "" });
    setDialogError("");
    setDialog({ kind: "adjust", item });
  }

  function handleAdjustSubmit(event: FormEvent) {
    event.preventDefault();

    if (dialog?.kind !== "adjust") {
      return;
    }

    const { item } = dialog;
    const amount = Number(adjustForm.quantity);

    run(
      () =>
        api.post(`/inventory/items/${item.id}/adjustments`, {
          quantity: String(
            adjustForm.direction === "remove" ? -amount : amount
          ),
          reason: adjustForm.reason.trim(),
        }),
      `Stock of ${item.name} was corrected.`,
      "Could not correct the stock."
    );
  }

  /* ---------------- filtering ---------------- */

  const query = search.trim().toLowerCase();

  const visible = items.filter((item) => {
    if (!showInactive && !item.is_active) {
      return false;
    }

    if (category !== "all" && item.category !== category) {
      return false;
    }

    if (lowOnly && !item.is_low_stock) {
      return false;
    }

    if (!matchesBranch(branchFilter, item.branch_id)) {
      return false;
    }

    if (!query) {
      return true;
    }

    return `${item.name} ${item.sku}`.toLowerCase().includes(query);
  });

  const activeItems = items.filter((item) => item.is_active);
  const lowCount = activeItems.filter((item) => item.is_low_stock).length;
  const inactiveCount = items.length - activeItems.length;

  function setItem<K extends keyof ItemForm>(
    key: K,
    value: ItemForm[K]
  ) {
    setItemForm((current) => ({ ...current, [key]: value }));
  }

  function setStock(key: keyof typeof stockForm, value: string) {
    setStockForm((current) => ({ ...current, [key]: value }));
  }

  /* ============================================================
     RENDER
  ============================================================ */

  return (
    <div className="space-y-6 p-6 md:p-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Inventory
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Coffins, flowers and supplies. Stock changes only by
            receiving, issuing, returning or correcting it, so every
            number can be explained.
          </p>
        </div>

        <button
          type="button"
          onClick={openCreate}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gray-800"
        >
          <Plus size={18} />
          Add Item
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

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-gray-500">Stocked items</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">
            {activeItems.length}
          </p>
        </div>

        <button
          type="button"
          onClick={() => setLowOnly((current) => !current)}
          aria-pressed={lowOnly}
          className={`rounded-xl border p-5 text-left shadow-sm transition ${
            lowOnly
              ? "border-amber-400 bg-amber-50"
              : "border-gray-200 bg-white hover:border-amber-300"
          }`}
        >
          <p className="flex items-center gap-1.5 text-sm text-gray-500">
            <AlertTriangle size={14} className="text-amber-500" />
            Low stock
          </p>
          <p
            className={`mt-1 text-3xl font-bold ${
              lowCount > 0 ? "text-amber-600" : "text-gray-900"
            }`}
          >
            {lowCount}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            {lowOnly ? "Showing only these. Click to clear." : "Click to show only these."}
          </p>
        </button>

        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-gray-500">Stock value</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">
            R{" "}
            {formatMoney(
              activeItems.reduce(
                (sum, item) =>
                  sum +
                  Number(item.quantity_on_hand) *
                    Number(item.unit_cost ?? 0),
                0
              )
            )}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            At each item&apos;s latest cost
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-md">
          <Search
            size={18}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by name or SKU..."
            aria-label="Search inventory"
            className="w-full rounded-lg border border-gray-300 bg-white py-3 pl-10 pr-4 text-sm outline-none focus:border-gray-500"
          />
        </div>

        <select
          aria-label="Filter by category"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-slate-900"
        >
          <option value="all">All categories</option>
          {CATEGORIES.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.label}
            </option>
          ))}
        </select>

        {branchData.multiple && (
          <BranchFilter
            branches={branchData.branches}
            value={branchFilter}
            onChange={setBranchFilter}
          />
        )}

        {inactiveCount > 0 && (
          <label className="flex items-center gap-2 text-sm text-slate-600">
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
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-gray-500">
          <Loader2 size={18} className="animate-spin" />
          Loading inventory…
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white px-6 py-14 text-center">
          <Boxes size={32} className="mx-auto text-gray-400" />
          <p className="mt-3 text-sm font-medium text-gray-700">
            {items.length === 0
              ? "No stock items yet. Add your first item."
              : "No items match these filters."}
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-3 font-medium">Item</th>
                <th className="px-5 py-3 font-medium">Category</th>
                <th className="px-5 py-3 text-right font-medium">
                  On hand
                </th>
                <th className="px-5 py-3 text-right font-medium">
                  Unit cost
                </th>
                <th className="px-5 py-3 font-medium">Supplier</th>
                <th className="px-5 py-3 text-right font-medium">
                  Actions
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {visible.map((item) => (
                <tr
                  key={item.id}
                  className={item.is_active ? "" : "opacity-60"}
                >
                  <td className="px-5 py-4">
                    <p className="font-medium text-slate-900">
                      {item.name}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {item.sku}
                      {!item.is_active && " · Inactive"}
                    </p>

                    {branchData.multiple && (
                      <div className="mt-1.5">
                        <BranchBadge
                          branchId={item.branch_id}
                          byId={branchData.byId}
                        />
                      </div>
                    )}
                  </td>

                  <td className="px-5 py-4 text-slate-600">
                    {categoryLabel(item.category)}
                  </td>

                  <td className="px-5 py-4 text-right">
                    <span className="font-semibold text-slate-900">
                      {formatQty(item.quantity_on_hand)}
                    </span>{" "}
                    <span className="text-xs text-slate-500">
                      {item.unit}
                    </span>

                    {item.is_low_stock && (
                      <div className="mt-1">
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                          <AlertTriangle size={12} />
                          Low · reorder at{" "}
                          {formatQty(item.reorder_level)}
                        </span>
                      </div>
                    )}
                  </td>

                  <td className="px-5 py-4 text-right text-slate-600">
                    {item.unit_cost
                      ? `R ${formatMoney(item.unit_cost)}`
                      : "—"}
                  </td>

                  <td className="px-5 py-4 text-slate-600">
                    {(item.supplier_id &&
                      supplierById.get(item.supplier_id)?.name) ||
                      "—"}
                  </td>

                  <td className="px-5 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        disabled={!item.is_active}
                        onClick={() => openStock(item, "receipt")}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                      >
                        <ArrowDownToLine size={14} />
                        Receive
                      </button>

                      <button
                        type="button"
                        disabled={!item.is_active}
                        onClick={() => openStock(item, "issue")}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                      >
                        <ArrowUpFromLine size={14} />
                        Issue
                      </button>

                      <button
                        type="button"
                        aria-label={`More for ${item.name}`}
                        onClick={() => {
                          setDialogError("");
                          setHistory(null);
                          setDialog({ kind: "detail", item });
                        }}
                        className="rounded-lg border border-slate-300 bg-white p-1.5 text-slate-600 hover:bg-slate-50"
                      >
                        <MoreHorizontal size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ---------------- create / edit ---------------- */}

      {(dialog?.kind === "create" || dialog?.kind === "edit") && (
        <Dialog
          title={dialog.kind === "create" ? "Add Item" : "Edit Item"}
          onClose={closeDialog}
          wide
        >
          <form onSubmit={handleItemSubmit} className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <Field
                label="SKU"
                hint={
                  dialog.kind === "edit"
                    ? "The SKU cannot be changed."
                    : "Your own code for this item, no spaces."
                }
              >
                <input
                  required
                  disabled={dialog.kind === "edit"}
                  value={itemForm.sku}
                  onChange={(event) =>
                    setItem("sku", event.target.value)
                  }
                  className={`${inputClass} disabled:bg-slate-100`}
                />
              </Field>

              <Field label="Name">
                <input
                  required
                  value={itemForm.name}
                  onChange={(event) =>
                    setItem("name", event.target.value)
                  }
                  className={inputClass}
                />
              </Field>

              <Field label="Category">
                <select
                  value={itemForm.category}
                  onChange={(event) =>
                    setItem("category", event.target.value)
                  }
                  className={inputClass}
                >
                  {CATEGORIES.map((entry) => (
                    <option key={entry.value} value={entry.value}>
                      {entry.label}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Unit" hint="e.g. each, box, litre">
                <input
                  required
                  value={itemForm.unit}
                  onChange={(event) =>
                    setItem("unit", event.target.value)
                  }
                  className={inputClass}
                />
              </Field>

              <Field label="Supplier">
                <select
                  value={itemForm.supplier_id}
                  onChange={(event) =>
                    setItem("supplier_id", event.target.value)
                  }
                  className={inputClass}
                >
                  <option value="">No supplier</option>
                  {suppliers
                    .filter(
                      (s) =>
                        s.is_active || s.id === itemForm.supplier_id
                    )
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                </select>
              </Field>

              <Field label="Unit cost (R)">
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={itemForm.unit_cost}
                  onChange={(event) =>
                    setItem("unit_cost", event.target.value)
                  }
                  className={inputClass}
                />
              </Field>

              <Field
                label="Reorder level"
                hint="Flagged as low stock at or below this. 0 turns it off."
              >
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={itemForm.reorder_level}
                  onChange={(event) =>
                    setItem("reorder_level", event.target.value)
                  }
                  className={inputClass}
                />
              </Field>

              {dialog.kind === "create" && (
                <Field
                  label="Opening stock"
                  hint="Already on the shelf. Recorded as a receipt."
                >
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={itemForm.opening_quantity}
                    onChange={(event) =>
                      setItem("opening_quantity", event.target.value)
                    }
                    className={inputClass}
                  />
                </Field>
              )}
            </div>

            {dialog.kind === "create" && branchData.multiple && (
              <BranchSelect
                branches={branchData.branches}
                value={itemForm.branch_id}
                onChange={(value) => setItem("branch_id", value)}
              />
            )}

            <Field label="Description">
              <textarea
                rows={2}
                value={itemForm.description}
                onChange={(event) =>
                  setItem("description", event.target.value)
                }
                className={inputClass}
              />
            </Field>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              submitLabel={
                dialog.kind === "create" ? "Add Item" : "Save"
              }
            />
          </form>
        </Dialog>
      )}

      {/* ---------------- receive / issue / return ---------------- */}

      {dialog?.kind === "stock" && (
        <Dialog
          title={`${STOCK_TITLES[dialog.mode]}: ${dialog.item.name}`}
          onClose={closeDialog}
        >
          <form onSubmit={handleStockSubmit} className="space-y-4">
            <p className="text-sm text-slate-600">
              On hand now:{" "}
              <strong>
                {formatQty(dialog.item.quantity_on_hand)}{" "}
                {dialog.item.unit}
              </strong>
            </p>

            <Field label={`Quantity (${dialog.item.unit})`}>
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                value={stockForm.quantity}
                onChange={(event) =>
                  setStock("quantity", event.target.value)
                }
                className={inputClass}
              />
            </Field>

            {dialog.mode === "receipt" ? (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Supplier">
                    <select
                      value={stockForm.supplier_id}
                      onChange={(event) =>
                        setStock("supplier_id", event.target.value)
                      }
                      className={inputClass}
                    >
                      <option value="">No supplier</option>
                      {suppliers
                        .filter((s) => s.is_active)
                        .map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name}
                          </option>
                        ))}
                    </select>
                  </Field>

                  <Field label="Unit cost (R)">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={stockForm.unit_cost}
                      onChange={(event) =>
                        setStock("unit_cost", event.target.value)
                      }
                      className={inputClass}
                    />
                  </Field>
                </div>

                <Field
                  label="Invoice or delivery note number"
                >
                  <input
                    value={stockForm.reference}
                    onChange={(event) =>
                      setStock("reference", event.target.value)
                    }
                    className={inputClass}
                  />
                </Field>
              </>
            ) : (
              <Field
                label="Case"
                hint={
                  dialog.mode === "issue"
                    ? "Which case this stock is used for."
                    : "Which case it came back from."
                }
              >
                <select
                  value={stockForm.case_id}
                  onChange={(event) =>
                    setStock("case_id", event.target.value)
                  }
                  className={inputClass}
                >
                  <option value="">No case</option>
                  {cases.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.case_number} · {entry.deceased_full_name}
                    </option>
                  ))}
                </select>
              </Field>
            )}

            <Field label="Note">
              <input
                value={stockForm.reason}
                onChange={(event) =>
                  setStock("reason", event.target.value)
                }
                className={inputClass}
              />
            </Field>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              submitLabel={
                { receipt: "Receive", issue: "Issue", return: "Return" }[
                  dialog.mode
                ]
              }
            />
          </form>
        </Dialog>
      )}

      {/* ---------------- adjust ---------------- */}

      {dialog?.kind === "adjust" && (
        <Dialog
          title={`Correct stock: ${dialog.item.name}`}
          onClose={closeDialog}
        >
          <form onSubmit={handleAdjustSubmit} className="space-y-4">
            <p className="text-sm text-slate-600">
              Use this after a stock count or for a loss or damage.
              On hand now:{" "}
              <strong>
                {formatQty(dialog.item.quantity_on_hand)}{" "}
                {dialog.item.unit}
              </strong>
              . A reason is always recorded.
            </p>

            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Change">
                <select
                  value={adjustForm.direction}
                  onChange={(event) =>
                    setAdjustForm((current) => ({
                      ...current,
                      direction: event.target.value,
                    }))
                  }
                  className={inputClass}
                >
                  <option value="remove">Remove stock</option>
                  <option value="add">Add stock</option>
                </select>
              </Field>

              <Field label={`Quantity (${dialog.item.unit})`}>
                <input
                  required
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={adjustForm.quantity}
                  onChange={(event) =>
                    setAdjustForm((current) => ({
                      ...current,
                      quantity: event.target.value,
                    }))
                  }
                  className={inputClass}
                />
              </Field>
            </div>

            <Field label="Reason">
              <input
                required
                value={adjustForm.reason}
                onChange={(event) =>
                  setAdjustForm((current) => ({
                    ...current,
                    reason: event.target.value,
                  }))
                }
                className={inputClass}
              />
            </Field>

            {dialogError && <ErrorNote message={dialogError} />}

            <DialogFooter
              onClose={closeDialog}
              saving={saving}
              submitLabel="Correct stock"
            />
          </form>
        </Dialog>
      )}

      {/* ---------------- detail + ledger ---------------- */}

      {dialog?.kind === "detail" && (
        <Dialog title={dialog.item.name} onClose={closeDialog} wide>
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={!dialog.item.is_active}
                onClick={() => openStock(dialog.item, "return")}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
              >
                Return stock
              </button>

              <button
                type="button"
                disabled={!dialog.item.is_active}
                onClick={() => openAdjust(dialog.item)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
              >
                Correct stock
              </button>

              <button
                type="button"
                onClick={() => openEdit(dialog.item)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                Edit
              </button>

              {branchData.multiple && (
                <button
                  type="button"
                  onClick={() => {
                    setDialogError("");
                    setDialog({ kind: "move", item: dialog.item });
                  }}
                  className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  Move to branch
                </button>
              )}

              {dialog.item.is_active ? (
                <button
                  type="button"
                  onClick={() => {
                    setDialogError("");
                    setDialog({
                      kind: "deactivate",
                      item: dialog.item,
                    });
                  }}
                  className="ml-auto px-2 py-1.5 text-xs font-medium text-red-600 hover:text-red-700"
                >
                  Deactivate
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() =>
                    run(
                      () =>
                        api.post(
                          `/inventory/items/${dialog.item.id}/reactivate`
                        ),
                      `${dialog.item.name} is active again.`,
                      "Could not reactivate the item."
                    )
                  }
                  className="ml-auto px-2 py-1.5 text-xs font-medium text-emerald-700 hover:text-emerald-800"
                >
                  Reactivate
                </button>
              )}
            </div>

            {dialogError && <ErrorNote message={dialogError} />}

            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-900">
                Stock history
              </h3>

              {history === null ? (
                <div className="flex items-center gap-2 py-6 text-sm text-slate-500">
                  <Loader2 size={16} className="animate-spin" />
                  Loading history…
                </div>
              ) : history.length === 0 ? (
                <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">
                  No stock movements yet.
                </p>
              ) : (
                <div className="max-h-80 overflow-y-auto rounded-lg border border-slate-200">
                  <table className="w-full text-left text-sm">
                    <thead className="sticky top-0 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-4 py-2 font-medium">When</th>
                        <th className="px-4 py-2 font-medium">What</th>
                        <th className="px-4 py-2 text-right font-medium">
                          Qty
                        </th>
                        <th className="px-4 py-2 text-right font-medium">
                          Balance
                        </th>
                        <th className="px-4 py-2 font-medium">Detail</th>
                      </tr>
                    </thead>

                    <tbody className="divide-y divide-slate-100">
                      {history.map((movement) => {
                        const linkedCase = movement.case_id
                          ? caseById.get(movement.case_id)
                          : undefined;

                        const detail = [
                          linkedCase
                            ? `Case ${linkedCase.case_number}`
                            : movement.case_id
                            ? "A case"
                            : null,
                          movement.supplier_id
                            ? supplierById.get(movement.supplier_id)
                                ?.name
                            : null,
                          movement.reference,
                          movement.reason,
                        ]
                          .filter(Boolean)
                          .join(" · ");

                        return (
                          <tr key={movement.id}>
                            <td className="whitespace-nowrap px-4 py-2 text-slate-500">
                              {formatDateTime(movement.created_at)}
                            </td>
                            <td className="px-4 py-2">
                              {MOVEMENT_LABELS[movement.movement_type]}
                            </td>
                            <td
                              className={`px-4 py-2 text-right font-medium ${
                                Number(movement.quantity) < 0
                                  ? "text-red-600"
                                  : "text-emerald-700"
                              }`}
                            >
                              {formatSignedQty(movement.quantity)}
                            </td>
                            <td className="px-4 py-2 text-right">
                              {formatQty(movement.balance_after)}
                            </td>
                            <td className="px-4 py-2 text-slate-600">
                              {detail || "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </Dialog>
      )}

      {/* ---------------- move to branch ---------------- */}

      {dialog?.kind === "move" && (
        <TransferDialog
          path={`/inventory/items/${dialog.item.id}/transfer`}
          subject={dialog.item.name}
          currentBranchId={dialog.item.branch_id}
          branches={branchData.branches}
          onClose={closeDialog}
          onMoved={(message) => {
            closeDialog();
            setNotice(message);
            reload();
          }}
        />
      )}

      {/* ---------------- deactivate ---------------- */}

      {dialog?.kind === "deactivate" && (
        <Dialog title="Deactivate item" onClose={closeDialog}>
          <form
            onSubmit={(event) => {
              event.preventDefault();

              run(
                () =>
                  api.post(
                    `/inventory/items/${dialog.item.id}/deactivate`
                  ),
                `${dialog.item.name} was deactivated.`,
                "Could not deactivate the item."
              );
            }}
            className="space-y-4"
          >
            <p className="text-sm text-slate-600">
              {dialog.item.name} can no longer take stock movements
              until you reactivate it. Its history is kept.
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
