/* Prices come from the API in cents, before VAT; this shows them in rands. */

export type Plan = {
  id: string;
  code: string;
  business_type: "funeral" | "general";
  name: string;
  tagline: string | null;
  base_price_cents: number;
  included_staff: number;
  included_branches: number;
  extra_staff_cents: number;
  extra_branch_cents: number;
  is_active: boolean;
};

export type PriceSettings = {
  currency: string;
  vat_percent: number;
  price_note: string | null;
};

export type PublicPricing = PriceSettings & {
  plans: { funeral: Plan[]; general: Plan[] };
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
  vat_percent: number;
  vat_cents: number;
  total_incl_vat_cents: number;
};

export type Subscription = PriceSettings & {
  tier: string;
  status: string;
  trial_ends_at: string | null;
  usage: Record<string, number>;
  plan: Plan;
  plan_chosen: boolean;
  plans: Plan[];
  next_staff_cents: number;
  next_staff_incl_vat_cents: number;
  next_branch_cents: number;
  next_branch_incl_vat_cents: number;
  bill?: {
    year: number;
    month: number;
    status: string;
    plan: string;
    peak_staff: number;
    peak_branches: number;
    vat_percent: number;
    list_total_cents: number;
    list_total_incl_vat_cents: number;
    amount_due_cents: number;
    vat_cents: number;
    amount_due_incl_vat_cents: number;
    note: string | null;
    lines: QuoteLine[];
    now: Quote;
  };
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

/** The price with VAT added, rounded to the cent like the server does. */
export function inclVat(cents: number, vatPercent: number): number {
  return cents + Math.floor((cents * vatPercent + 50) / 100);
}

export function monthLabel(year: number, month: number): string {
  return new Date(year, month - 1, 1).toLocaleDateString("en-ZA", {
    month: "long",
    year: "numeric",
  });
}
