import api from "@/lib/api";
import { day, esc, money, printHtml } from "@/lib/printDocument";

export type SalesLine = {
  id?: string;
  description: string;
  quantity: number;
  unit_price: number;
  line_total?: number;
};

export type SalesPayment = {
  id: string;
  amount: number;
  method: string;
  reference: string | null;
  paid_on: string;
  status: string;
  void_reason: string | null;
};

export type SalesDoc = {
  id: string;
  customer_id: string;
  customer_name: string;
  document_type: "quote" | "invoice";
  status: string;
  number: string | null;
  issue_date: string | null;
  due_date: string | null;
  valid_until: string | null;
  subtotal: number;
  discount: number;
  tax: number;
  total: number;
  notes: string | null;
  source_quote_id: string | null;
  void_reason: string | null;
  paid: number;
  balance: number;
  state: "unpaid" | "partial" | "paid" | null;
  days_overdue: number;
  lines?: SalesLine[];
  payments?: SalesPayment[];
  customer?: {
    id: string;
    name: string;
    phone: string | null;
    email: string | null;
    address: string | null;
    tax_number: string | null;
  } | null;
};

export type Customer = {
  id: string;
  name: string;
  phone: string | null;
  email: string | null;
  address: string | null;
  tax_number: string | null;
  notes: string | null;
  archived: boolean;
  owes?: number;
};

/** A short phrase for where a document stands. */
export function docStatusLabel(d: SalesDoc): string {
  if (d.status === "void") return "Voided";
  if (d.status === "draft") return "Draft";
  if (d.document_type === "quote") {
    return d.status === "accepted"
      ? "Accepted"
      : d.status === "declined"
        ? "Declined"
        : "Sent";
  }
  if (d.state === "paid") return "Paid";
  if (d.days_overdue > 0) return `Overdue ${d.days_overdue}d`;
  return d.state === "partial" ? "Part paid" : "Unpaid";
}

export function docStatusTone(d: SalesDoc): string {
  const label = docStatusLabel(d);
  if (label === "Paid" || label === "Accepted") return "bg-emerald-100 text-emerald-800";
  if (label.startsWith("Overdue")) return "bg-red-100 text-red-800";
  if (label === "Voided" || label === "Declined") return "bg-slate-200 text-slate-600";
  if (label === "Draft") return "bg-slate-100 text-slate-700";
  return "bg-amber-100 text-amber-800";
}

export async function printSalesDocument(
  doc: SalesDoc,
  businessId: string,
): Promise<void> {
  const business = await api
    .get(`/businesses/${businessId}`)
    .then((r) => r.data)
    .catch(() => ({}));

  const invoice = doc.document_type === "invoice";
  const kind = invoice ? "INVOICE" : "QUOTE";
  const c = doc.customer;

  const rows = (doc.lines ?? [])
    .map(
      (l) => `<tr><td>${esc(l.description)}</td><td class="n">${esc(l.quantity)}</td>
      <td class="n">${money(l.unit_price)}</td><td class="n">${money(l.line_total ?? 0)}</td></tr>`,
    )
    .join("");

  const html = `<!doctype html><html><head><meta charset="utf-8">
<title>${kind} ${esc(doc.number ?? "")}</title>
<style>
  body{font-family:Arial,Helvetica,sans-serif;color:#111;margin:32px;font-size:13px}
  h1{font-size:26px;margin:0}
  .top{display:flex;justify-content:space-between;gap:24px;margin-bottom:24px}
  .muted{color:#555}
  table{width:100%;border-collapse:collapse;margin-top:16px}
  th{background:#f2f2f2;text-align:left}
  th,td{border-bottom:1px solid #ddd;padding:8px}
  .n{text-align:right;white-space:nowrap}
  .tot{margin-left:auto;margin-top:16px;width:260px}
  .tot div{display:flex;justify-content:space-between;padding:3px 0}
  .grand{border-top:2px solid #111;font-weight:bold;font-size:15px;margin-top:4px;padding-top:6px!important}
  .box{margin-top:24px;padding:10px;background:#f7f7f7}
  .flag{font-weight:bold;margin-top:8px}
</style></head><body>
<div class="top">
  <div>
    <strong style="font-size:16px">${esc(business.name)}</strong><br>
    <span class="muted">${esc(business.address ?? "")}</span><br>
    <span class="muted">${esc([business.phone, business.email].filter(Boolean).join(" · "))}</span>
  </div>
  <div style="text-align:right">
    <h1>${kind}</h1>
    <div>${esc(doc.number ?? "Draft")}</div>
    <div class="muted">Date: ${esc(day(doc.issue_date))}</div>
    ${invoice && doc.due_date ? `<div class="muted">Due: ${esc(day(doc.due_date))}</div>` : ""}
    ${!invoice && doc.valid_until ? `<div class="muted">Valid until: ${esc(day(doc.valid_until))}</div>` : ""}
    ${doc.status === "draft" ? `<div class="flag" style="color:#b00">DRAFT - not issued</div>` : ""}
    ${doc.status === "void" ? `<div class="flag" style="color:#b00">VOID</div>` : ""}
    ${doc.state === "paid" ? `<div class="flag" style="color:#070">PAID</div>` : ""}
  </div>
</div>
<div><span class="muted">${invoice ? "Billed to" : "Prepared for"}</span><br>
  <strong>${esc(c?.name ?? doc.customer_name)}</strong><br>
  <span class="muted">${esc(c?.address ?? "")}</span><br>
  <span class="muted">${esc([c?.phone, c?.email].filter(Boolean).join(" · "))}</span>
  ${c?.tax_number ? `<br><span class="muted">Tax no: ${esc(c.tax_number)}</span>` : ""}
</div>
<table><thead><tr><th>Description</th><th class="n">Qty</th><th class="n">Price</th><th class="n">Amount</th></tr></thead>
<tbody>${rows}</tbody></table>
<div class="tot">
  <div><span>Subtotal</span><span>${money(doc.subtotal)}</span></div>
  ${doc.discount ? `<div><span>Discount</span><span>- ${money(doc.discount)}</span></div>` : ""}
  ${doc.tax ? `<div><span>Tax</span><span>${money(doc.tax)}</span></div>` : ""}
  <div class="grand"><span>Total</span><span>${money(doc.total)}</span></div>
  ${invoice && doc.paid ? `<div><span>Paid</span><span>- ${money(doc.paid)}</span></div><div><strong>Balance due</strong><strong>${money(doc.balance)}</strong></div>` : ""}
</div>
${doc.notes ? `<div class="box">${esc(doc.notes)}</div>` : ""}
${invoice && doc.balance > 0 && business.payment_instructions ? `<div class="box"><strong>How to pay</strong><br>${esc(business.payment_instructions).replace(/\n/g, "<br>")}</div>` : ""}
</body></html>`;

  printHtml(html);
}
