# Customers, sales and bills (general businesses)

A general business (not a funeral home) can sell to customers without any
funeral case.

- **Customers** (`/customers`): name, contact, tax number, notes. Archive, never delete.
- **Quotes and invoices** (`/sales`): draft -> issue (gets a number) -> payments.
  Tax is added automatically when it is on in Settings. A quote can be accepted,
  declined or converted into an invoice. Print from the document page.
- **Payments**: recorded against an invoice, never deleted (cancel with a reason).
  Each payment also appears in Money received, so profit and loss stays right.
- **Who owes you** (`/receivables`): unpaid invoices with ageing buckets.
- **Bills you owe** (`/bills`): supplier bills. Paying one records an expense.
- **Overdue alerts**: the daily overdue job notifies main admin, managers and
  finance about overdue invoices and bills.

Permissions: `customers.*`, `sales.*`, `bills.*` (general businesses only; hidden
for funeral homes). Manager and finance hold them; staff may view customers.

API: `/customers`, `/sales/documents`, `/sales/documents/{id}/(issue|accept|decline|convert|void|payments)`,
`/sales/payments/{id}/void`, `/sales/receivables`, `/bills`.

## Reports, recurring items and budgets

- **Reports** (`/business-reports`): profit and loss for any period (cash basis),
  sales by customer, tax charged on invoices, month by month; print or download as CSV
  for Excel. API: `/business-reports/overview`, `/business-reports/export`.
- **Recurring items** (`/planning`): rent, salaries or a retainer entered once; the hourly
  `recurring` job records them on schedule (catches up missed periods, at most 12 at a time,
  never twice). Stopping one never changes entries already recorded.
- **Budgets**: a monthly amount per expense category, warned at 80% and when used up
  (one notification per state per month).
