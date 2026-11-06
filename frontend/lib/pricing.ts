/* Prices come from the API in cents; this turns them into rands. */

export type Pricing = {
  currency: string;
  base_price_cents: number;
  included_staff: number;
  included_branches: number;
  extra_staff_cents: number;
  extra_branch_cents: number;
  price_note: string | null;
};

export type QuoteLine = {
  label: string;
  detail: string;
  quantity: number;
  unit_cents: number;
  amount_cents: number;
};

export type Quote = {
  staff: number;
  branches: number;
  extra_staff: number;
  extra_branches: number;
  lines: QuoteLine[];
  total_cents: number;
};

/** 29900 -> "R299", 2550 -> "R25.50" (no decimals when whole). */
export function rands(cents: number | null | undefined): string {
  const value = (cents ?? 0) / 100;
  const whole = Number.isInteger(value);
  const text = value.toLocaleString("en-ZA", {
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: 2,
  });
  return `R${text.replace(/ /g, " ")}`;
}

export function monthLabel(year: number, month: number): string {
  return new Date(year, month - 1, 1).toLocaleDateString("en-ZA", {
    month: "long",
    year: "numeric",
  });
}

export type Subscription = {
  tier: string;
  status: string;
  trial_ends_at: string | null;
  usage: Record<string, number>;
  pricing: Pricing;
  next_staff_cents: number;
  next_branch_cents: number;
  bill?: {
    year: number;
    month: number;
    status: string;
    peak_staff: number;
    peak_branches: number;
    list_total_cents: number;
    amount_due_cents: number;
    note: string | null;
    lines: QuoteLine[];
    now: Quote;
  };
};
