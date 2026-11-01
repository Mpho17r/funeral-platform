import api from "@/lib/api";

type PrintLine = {
  description: string;
  quantity: string;
  unit_price: string;
  line_total: string;
};

export type PrintableDocument = {
  case_id: string;
  document_type: "quote" | "invoice";
  number: string | null;
  status: string;
  subtotal: string;
  discount: string;
  tax: string;
  total: string;
  due_date: string | null;
  valid_until: string | null;
  issued_at: string | null;
  notes: string | null;
  created_at: string;
  lines: PrintLine[];
};

export function esc(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function money(value: string | number): string {
  return `R ${Number(value).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function day(value: string | null): string {
  return value ? new Date(value).toLocaleDateString("en-ZA") : "";
}

/**
 * Prints a quote or invoice as a clean page: the business details at the
 * top, the lines, the totals and - on an invoice - what is still owed.
 * It uses a hidden frame, so no pop-up is opened and nothing else on the
 * screen is printed.
 */
export async function printFinancialDocument(
  doc: PrintableDocument,
  businessId: string,
): Promise<void> {
  const [business, theCase] = await Promise.all([
    api.get(`/businesses/${businessId}`).then((r) => r.data).catch(() => ({})),
    api.get(`/cases/${doc.case_id}`).then((r) => r.data).catch(() => ({})),
  ]);

  const kind = doc.document_type === "invoice" ? "Invoice" : "Quote";
  const draft = doc.status === "draft";

  const rows = doc.lines
    .map(
      (l) => `<tr><td>${esc(l.description)}</td>
        <td class="n">${esc(Number(l.quantity))}</td>
        <td class="n">${money(l.unit_price)}</td>
        <td class="n">${money(l.line_total)}</td></tr>`,
    )
    .join("");

  const html = `<!doctype html><html><head><meta charset="utf-8">
<title>${esc(kind)} ${esc(doc.number ?? "")}</title>
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
  .draft{color:#b00;font-weight:bold;margin-top:8px}
  .notes{margin-top:24px;padding:10px;background:#f7f7f7}
</style></head><body>
<div class="top">
  <div>
    <strong style="font-size:16px">${esc(business.name)}</strong><br>
    <span class="muted">${esc(business.address ?? "")}</span><br>
    <span class="muted">${esc([business.phone, business.email].filter(Boolean).join(" · "))}</span>
  </div>
  <div style="text-align:right">
    <h1>${esc(kind.toUpperCase())}</h1>
    <div>${esc(doc.number ?? "Not numbered yet")}</div>
    <div class="muted">Date: ${esc(day(doc.issued_at ?? doc.created_at))}</div>
    ${
      doc.document_type === "invoice" && doc.due_date
        ? `<div class="muted">Due: ${esc(day(doc.due_date))}</div>`
        : ""
    }
    ${
      doc.document_type === "quote" && doc.valid_until
        ? `<div class="muted">Valid until: ${esc(day(doc.valid_until))}</div>`
        : ""
    }
    ${draft ? `<div class="draft">DRAFT - not issued</div>` : ""}
  </div>
</div>
<div><span class="muted">For the family of</span><br>
  <strong>${esc(theCase.deceased_full_name ?? "")}</strong>
  ${theCase.case_number ? `<span class="muted"> · Case ${esc(theCase.case_number)}</span>` : ""}
</div>
<table><thead><tr><th>Description</th><th class="n">Qty</th><th class="n">Price</th><th class="n">Amount</th></tr></thead>
<tbody>${rows}</tbody></table>
<div class="tot">
  <div><span>Subtotal</span><span>${money(doc.subtotal)}</span></div>
  ${Number(doc.discount) ? `<div><span>Discount</span><span>- ${money(doc.discount)}</span></div>` : ""}
  ${Number(doc.tax) ? `<div><span>Tax</span><span>${money(doc.tax)}</span></div>` : ""}
  <div class="grand"><span>Total</span><span>${money(doc.total)}</span></div>
</div>
${doc.notes ? `<div class="notes">${esc(doc.notes)}</div>` : ""}
${
  business.payment_instructions && doc.document_type === "invoice"
    ? `<div class="notes"><strong>How to pay</strong><br>${esc(business.payment_instructions).replace(/\n/g, "<br>")}</div>`
    : ""
}
</body></html>`;

  printHtml(html);
}

/** Prints a finished HTML page through a hidden frame (no pop-up). */
export function printHtml(html: string): void {
  const frame = document.createElement("iframe");
  frame.style.cssText =
    "position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden";
  document.body.appendChild(frame);

  const win = frame.contentWindow;
  if (!win) {
    frame.remove();
    throw new Error("Could not open the print view.");
  }

  win.document.open();
  win.document.write(html);
  win.document.close();

  // Give the frame a moment to lay out before the print dialog opens.
  setTimeout(() => {
    win.focus();
    win.print();
    setTimeout(() => frame.remove(), 2000);
  }, 250);
}
