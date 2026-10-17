export type Supplier = {
  id: string;
  business_id: string;
  name: string;
  contact_person: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type InventoryItem = {
  id: string;
  business_id: string;
  branch_id: string | null;
  supplier_id: string | null;
  sku: string;
  name: string;
  category: string;
  unit: string;
  description: string | null;
  quantity_on_hand: string;
  reorder_level: string;
  unit_cost: string | null;
  is_low_stock: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type StockMovement = {
  id: string;
  item_id: string;
  movement_type: "receipt" | "issue" | "return" | "adjustment";
  quantity: string;
  balance_after: string;
  unit_cost: string | null;
  supplier_id: string | null;
  case_id: string | null;
  reference: string | null;
  reason: string | null;
  created_by: string | null;
  created_at: string;
};

export const CATEGORIES: { value: string; label: string }[] = [
  { value: "coffin", label: "Coffins" },
  { value: "casket", label: "Caskets" },
  { value: "flowers", label: "Flowers" },
  { value: "clothing", label: "Clothing" },
  { value: "consumable", label: "Consumables" },
  { value: "stationery", label: "Stationery" },
  { value: "other", label: "Other" },
];

export function categoryLabel(value: string): string {
  return (
    CATEGORIES.find((category) => category.value === value)?.label ??
    value
  );
}

export const MOVEMENT_LABELS: Record<string, string> = {
  receipt: "Received",
  issue: "Issued",
  return: "Returned",
  adjustment: "Adjusted",
};

/** Quantities arrive as decimal strings ("3.00"); show them plainly. */
export function formatQty(value: string | number): string {
  return Number(value).toLocaleString("en-GB", {
    maximumFractionDigits: 2,
  });
}

/** Signed, so a ledger line reads +4 or -2. */
export function formatSignedQty(value: string | number): string {
  const number = Number(value);

  return `${number > 0 ? "+" : ""}${formatQty(number)}`;
}
