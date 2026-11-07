# Saccharum HQ — Finance & Compliance Technical Specification

**Status:** Proposed operating and technical design; not an implemented accounting, payroll, tax or banking system.
**Company model:** Proposed Saccharum Technologies (Pty) Ltd, subject to CIPC registration and name availability.
**Ownership:** Founder intends to hold 100% of shares and act as director.
**Founder compensation:** Salary is the selected primary compensation method.
**Accounting:** Hybrid — founder maintains day-to-day records and HQ workflows; a qualified accountant reviews the books, tax treatment, payroll setup and statutory submissions.
**Currency:** ZAR by default; all transactions retain an explicit currency.
**Related architecture:** [Saccharum HQ Architecture and Delivery Blueprint](SACCHARUM_HQ_ARCHITECTURE.md).

> This is a design document, not legal or tax advice and not evidence that Saccharum has been registered. It does not register the company, open accounts, appoint an accountant, create an employment relationship or submit anything to CIPC or SARS. Confirm current rules, rates, thresholds, due dates and payroll applicability with official guidance and the company's accountant.

## 1. Purpose and operating principles

The Finance & Compliance workspace must answer: how much cash has actually arrived; how much is restricted or owed; what the company has invoiced, earned and spent; what can safely be allocated; what the founder can be paid; and which obligations are approaching.

Principles:
- One legal entity with multiple management cost centres. LINDA, Khezwo, Loka and Saccharum Services are product views, not separate legal entities by default.
- Cash, invoiced revenue, accounting profit, restricted liabilities and available cash are distinct measures.
- An invoice or active subscription is not proof that cash has been received.
- Posted financial entries are corrected through reversals and adjustment entries, never silent edits.
- Founder pay is documented, approved and processed through an accountant-reviewed payroll process.
- Tax and payroll reserves are not working capital.
- HQ prepares records and workflows; it does not replace SARS, CIPC, a bank, a payroll provider or professional advice.
- Every dashboard number shows its period, currency, source, status and last refresh time.

## 2. Legal entity and governance foundation

Proposed profile, subject to registration and review:
- Private company, proposed name Saccharum Technologies (Pty) Ltd.
- Founder as sole shareholder (100%) and director.
- Standard MOI initially, unless legal advice indicates otherwise.
- Software development, SaaS subscriptions, technology services and support as business activities.
- February financial year-end is a proposal only; confirm with the accountant.
- Company bank account in the registered entity's name.
- Double-entry bookkeeping and product cost centres.

Do not describe the company as registered until CIPC issues incorporation evidence. Maintain the incorporation certificate, MOI, securities/share register, beneficial ownership information, director records, annual-return evidence and other statutory records. Track filing deadlines and changes in the compliance calendar, verifying current CIPC procedures before submission.

### Intellectual property and contracts

Create an asset and rights register for LINDA, Khezwo, Loka, Saccharum website assets, source code, brands, domains, documentation, third-party libraries, licences, contractor contributions and customer deliverables. Do not assume pre-incorporation assets automatically belong to the company. Record current owner, origin, licence/assignment status, date, agreement and reviewer. Obtain appropriate IP assignment or licence documents and professional review.

Store or reference CIPC records, share/director records, beneficial ownership evidence, bank confirmation, SARS registration, founder remuneration agreement, customer terms, privacy and operator agreements, supplier contracts, accounting policies, annual financial statements, tax acknowledgements and IP records with appropriate access controls.

## 3. Accounting model and chart of accounts

Use double-entry accounting. HQ may provide a management subledger, but the accountant-approved accounting platform remains the authoritative statutory books unless a formal decision changes this.

| Account group | Example accounts |
| --- | --- |
| Assets | Operating bank, reserve bank, provider clearing, receivables, prepaid expenses, equipment |
| Liabilities | VAT control/payable, PAYE, UIF, SDL where applicable, supplier payables, accrued expenses, customer credits |
| Equity | Share capital, retained earnings, current-year profit/loss, approved dividends if ever applicable |
| Revenue | LINDA subscriptions, setup fees, support, software development, other services |
| Direct costs | Product hosting, payment processing, transactional email/SMS, product infrastructure |
| Operating expenses | Domains, shared hosting, software, accounting, legal, insurance, marketing, bank fees |
| Payroll | Gross salaries, employer payroll costs, benefits and reimbursements with correct accounting treatment |
| Tax | Company income-tax expense and other applicable tax expense accounts |
| Control accounts | Unallocated receipts, unidentified bank items, provider clearing and reconciliation differences |

The accountant approves account codes and tax mappings. Do not conceal VAT or payroll liabilities in a generic expense account.

### Product cost centres

Use LINDA, Khezwo, Loka, Saccharum Services and Corporate/shared operations. Every transaction receives a cost centre or an explicit reason why it is shared. Shared costs use a documented allocation basis such as usage, headcount, revenue or direct attribution. Show the basis and permit accountant-reviewed corrections.

### Required transaction fields

Immutable ID; transaction type; transaction/invoice/settlement dates; counterparty; amount in integer minor units; ISO currency; VAT/tax code and rule version; gross, tax and net values; product cost centre; ledger account; source system and external reference; evidence attachment; creator/approver; posting state; reconciliation state; audit history.

## 4. Revenue, subscriptions and reconciliation

Represent the lifecycle separately: charge due; invoice/statement issued; payment initiated; provider confirms success; provider settles net of fees/refunds; bank confirms deposit; receipt allocated; reconciliation completed or exception raised.

A product entitlement may be active while settlement is pending. HQ must not confuse entitlement status with cash settlement.

Reconcile three sources:
1. LINDA/product subscription ledger.
2. Payment-provider transaction and settlement report.
3. Company bank statement.

Store gross payment, VAT component, provider fee, refund/chargeback, net settlement, settlement date and bank deposit separately. Use idempotency keys and external IDs to prevent duplicate receipts. Unmatched or partial settlements enter an exception queue with owner, age, reason and evidence.

Show MRR/ARR, invoiced revenue, recognised revenue, cash received, receivables, provider fees, refunds, chargebacks and net settlements separately. MRR/ARR are management run-rate metrics, not bank balances or proof of recognised accounting revenue. Never infer cash collected from an invoice or subscription statement.

## 5. Cash management and allocation policy

### Monthly cash waterfall

1. Reconcile receipts, provider settlements, bank deposits, refunds and chargebacks.
2. Identify restricted liabilities such as VAT and payroll deductions where applicable.
3. Pay approved essential costs: hosting, backups, domains, email, security, processing and critical suppliers.
4. Fund approved payroll, including applicable employer costs and deductions.
5. Update estimated company income-tax provision using accountant-reviewed taxable-profit forecasts.
6. Build and maintain a reserve target of three months of essential operating costs.
7. Allocate approved product development and growth spending.
8. Calculate remaining unrestricted cash only after all preceding controls.

This is a decision-support workflow, not an automatic transfer instruction. All payments remain subject to available funds, approvals, bank controls and accountant review.

### Cash buckets

Initially one company operating account may receive receipts, but HQ must track distinct ledger balances and reserve targets. As soon as affordable and practical, use separate company savings/reserve accounts for tax and operating reserves. Bank separation does not replace bookkeeping.

- Operating: approved routine company expenses.
- Tax reserve: estimated company income tax.
- VAT reserve: VAT collected less eligible input VAT, subject to registration and accountant review.
- Payroll reserve: payroll funding and applicable deductions/contributions.
- Emergency reserve: target of three months of essential operating costs.
- Growth reserve: approved product development, sales and infrastructure investment.

Never use VAT or payroll deductions as working capital. Do not transfer money into reserves if this would cause the company to miss a due obligation.

### Allocation calculations

The engine is configurable; percentages are not legal or tax rules.

- Reconciled available cash = cleared bank cash + confirmed provider clearing balances − outstanding payments − restricted cash/liabilities.
- Reserve gap = max(0, approved reserve target − eligible reserve balance).
- Tax provision = accountant-approved estimate based on forecast taxable profit and applicable tax profile, less amounts already paid/provisioned.
- Discretionary cash = reconciled available cash − due essential obligations − payroll funding − tax/VAT/payroll reserves − approved reserve top-up − approved near-term commitments.

If discretionary cash is negative, show the shortfall and block discretionary allocation recommendations. Never derive available cash from MRR or unpaid invoices.

### Founder salary and personal savings

The selected model is a documented founder salary, not informal withdrawals.

- Establish a written remuneration arrangement appropriate to the founder's director status and actual role.
- Approve a gross monthly salary only when the company can sustainably fund it.
- Use an accountant/payroll provider to determine PAYE, UIF, SDL and other applicable treatment. Director/shareholder status can affect the analysis; do not assume every payroll rule applies identically.
- Record gross salary, employer costs, deductions, net pay, payslip, submissions and payment evidence.
- Pay net salary to the founder's personal bank account on a consistent approved date.
- Personal purchases are paid from the personal account, not the company card/account.
- Reimburse only genuine business expenses supported by receipts and a business purpose.
- Salary changes require documented approval and an affordability review.

Personal savings goals and holidays are funded from personal after-tax salary or a properly approved distribution where legally available. They are not company expenses and must never be funded from VAT, payroll deductions, tax reserves, customer funds or operating capital.

## 6. South African tax and statutory workspace

The tax module is a calendar, evidence register, workpaper and review workflow. It is not an automated replacement for SARS eFiling or professional advice.

### Company income tax
Track SARS reference and eFiling status; provisional estimates and IRP6 references; payment approvals and proof; annual ITR14, financial statements and schedules. Keep accounting profit separate from taxable income. Calculate management estimates only using accountant-approved assumptions and rules effective for the relevant year. Rates and provisional-tax due dates must be verified against current SARS guidance.

### VAT
Track registration status (not registered, application pending, registered, cancelled/deregistered), effective date, taxable turnover over the applicable rolling period, tax periods, filing frequency and effective-dated rate/treatment versions. Capture output VAT, eligible input VAT, credit notes, adjustments and supporting tax invoices. Prepare reconciliations and review packs; track VAT201 reference, submission state and proof of payment/refund. Do not charge VAT or claim input VAT merely because a VAT field exists in HQ. Apply VAT according to actual registration and transaction treatment. Thresholds, rates, conditions and dates must be verified against current SARS guidance.

### Payroll taxes
Track employer registration and references for applicable obligations. Maintain restricted employee/director profiles. Record payroll periods, gross-to-net, payslips, deduction liabilities, employer costs, EMP201 and annual reconciliation evidence where applicable. Track PAYE, UIF, SDL and other obligations only where the company's actual circumstances make them applicable. Confirm director/shareholder classification and UIF/SDL treatment with the accountant before automating calculations.

### CIPC and governance
Track annual returns, beneficial ownership filings/updates, financial statement preparation and approval, director/shareholder changes, company-detail changes, statutory register updates and renewals. Distinguish reminder, prepared, submitted and accepted/complete states.

### Obligation record

Each obligation stores authority, type, entity, reporting period, due date, owner, reviewer, estimate and estimate source, status, submission/payment reference, evidence, rule source/effective date and audit history. Suggested statuses: upcoming, preparing, review required, approved, submitted, accepted, paid, reconciled, overdue, not applicable.

## 7. Expenses, suppliers and recurring commitments

Expense workflow: capture bill/receipt; assign supplier, category, cost centre and VAT treatment; attach evidence and business purpose; check duplicates and budget; submit for approval; record payment; reconcile bank entry; export/post to accounting system.

Track VPS/hosting, backups, domains, email, monitoring, software, accounting, legal, insurance and payment-provider commitments. Store renewal date, amount/currency, owner, cancellation notice, criticality and contract evidence. Recurring bills are not automatically approved; amount changes and new commitments trigger review.

## 8. Proposed HQ screens

### Finance overview
Bank balances and last reconciliation; reconciled available versus restricted cash; MRR, invoiced revenue and cash collected separately; expenses and accounting profit; net cash movement; upcoming bills/payroll/tax dates; reserve balances versus targets; runway assumptions; stale data and reconciliation warnings.

### Revenue and reconciliation
Customer/product/plan/invoice timeline; provider transactions, fees, refunds and settlements; bank matching and exception resolution; receipt allocation; monthly revenue and settlement export.

### Expenses and suppliers
Bills inbox, receipt capture, supplier register, recurring commitments, cost-centre allocation, approval queue and budget-versus-actual.

### Payroll and founder compensation
Restricted payroll workspace; gross salary, employer costs, deductions, net pay and payslip history; submission/payment evidence; affordability and approval history. No general dashboard exposure of personal payroll data.

### Tax and compliance
Obligation calendar; VAT reconciliation; provisional/annual company-tax workpapers; payroll obligations; CIPC filing tracker; evidence packs and accountant sign-off.

### Reserves and cash planning
Cash buckets, target balances, three-month reserve progress, cash waterfall preview, editable assumptions, 30/60/90-day forecast and shortfall warnings.

### Accountant workspace
Read-only access by default to approved records; review comments, adjustment requests, sign-off and period-close checklist. Payroll/tax access is explicitly granted only where required. No unilateral bank-detail changes or payment release by default.

## 9. Core data model

| Entity | Purpose |
| --- | --- |
| LegalEntity | Registered name, registration number, tax profile, year-end, status |
| ShareholderRecord / DirectorRecord | Ownership, share class, appointment dates, authority and evidence |
| BankAccount / BankTransaction | Masked account identity, account purpose, statement transactions and match state |
| LedgerAccount / JournalEntry / JournalLine | Double-entry ledger, period, debit/credit, source, cost centre and posting state |
| ProductCostCentre | Product and allocation policy |
| CustomerInvoice / InvoiceLine / Receipt | Customer, product, period, amounts, tax code, due date and allocation |
| ProviderSettlement | Batch, gross, fees, refunds, net and bank deposit |
| Expense / SupplierBill / Supplier | Category, cost centre, evidence, due date and approval |
| RecurringCommitment | Contract, amount, frequency, renewal and cancellation dates |
| TaxProfile / TaxRuleVersion | Registration, effective dates, filing frequency, rule source and reviewer |
| TaxObligation | Authority, period, deadline, estimate, status, owner and evidence |
| PayrollRun / Payslip | Period, gross, deductions, employer costs, net and evidence |
| FounderRemuneration | Approved gross amount, effective date, agreement and review history |
| CashBucket / ReserveTarget | Purpose, eligible balance, target, restrictions and policy version |
| CashAllocationRun | Inputs, waterfall outputs, assumptions, warnings and approver |
| Approval | Action, amount, requester, approver, decision and timestamp |
| EvidenceDocument | File reference, hash, retention class and access policy |
| ReconciliationException | Source records, difference, owner, age and resolution |
| ComplianceEvent | Obligation, deadline, reminder, escalation and completion evidence |

Money uses integer minor units and explicit currency. Sensitive payroll/tax records require field-level permissions and audited reads/exports.

## 10. API surface

Version endpoints under /api/v1. Final route names may change during implementation; preserve the domain boundaries.

| Area | Example endpoint |
| --- | --- |
| Overview | GET /finance/overview; GET /finance/cash-position; GET /finance/runway |
| Revenue | GET /revenue/invoices; GET /revenue/receipts; GET /revenue/settlements |
| Reconciliation | GET /reconciliation/exceptions; POST /reconciliation/matches |
| Expenses | GET/POST /expenses; POST /expenses/{id}/submit; POST /expenses/{id}/approve |
| Suppliers | GET/POST /suppliers; GET /commitments |
| Cash buckets | GET /cash-buckets; POST /cash-buckets/{id}/transfers/propose |
| Allocation | POST /cash-allocation-runs/preview; POST /cash-allocation-runs/{id}/approve |
| Payroll | GET/POST /payroll/runs; POST /payroll/runs/{id}/submit-for-review |
| Founder pay | GET /founder-remuneration; POST /founder-remuneration/proposals |
| Tax | GET /tax/obligations; POST /tax/obligations/{id}/evidence |
| Compliance | GET /compliance/calendar; GET /compliance/obligations/{id} |
| Period close | POST /periods/{period}/close-checklist; POST /periods/{period}/request-accountant-review |
| Audit | GET /audit/finance-events; GET /audit/access-events |

Writes validate role, state transition, amount limits, idempotency key and evidence requirements. Every state change returns a durable operation ID and creates an audit event.

## 11. Roles, approvals and security

| Role | Access |
| --- | --- |
| Owner / Director | Company overview and approval authority; MFA and step-up authentication for sensitive actions |
| Finance Operator | Capture and reconcile finance records; cannot approve own high-risk transactions |
| Accountant / Reviewer | Review and export approved books/tax evidence; no unilateral bank-detail changes |
| Payroll Administrator | Restricted payroll preparation and evidence only |
| Auditor | Read-only, time-limited access to approved records and audit trail |
| Engineering | Integration health only; no default access to payroll, bank details or tax documents |

Require separate requester/approver for configured high-risk payments/refunds; independent verification and second approval for bank-detail changes; documented approval for salary/payroll changes; accountant review before tax submission; reasoned reversal/adjustment entries; audit of access grants and sensitive exports.

A one-person company may not be able to provide internal dual control. Record that limitation and use an external accountant/bank approval process where practical rather than pretending maker-checker separation exists.

Security controls: MFA for privileged roles; encryption in transit/at rest; masked bank identifiers; no online-banking passwords or OTPs stored; provider/SARS/CIPC secrets kept in a secrets manager, never source control or ordinary application tables; audit creation, posting, reversal, approval, export, payroll access, tax evidence access, bank-detail and role changes; least-privilege access; reviewed retention; independent encrypted off-site backups and tested restores.

## 12. Reports and management packs

Monthly pack:
1. MRR, invoiced revenue, cash collected, expenses, accounting profit and net cash movement.
2. Customer/subscription movement by product.
3. Payment-provider and bank reconciliation.
4. Expenses and supplier commitments by cost centre.
5. Bank balances, restricted liabilities and reserve adequacy.
6. Payroll/founder remuneration summary with restricted details.
7. Tax estimates, due dates, filing and payment evidence.
8. 30/60/90-day cash forecast and assumptions.
9. Product contribution and shared-cost allocation.
10. Risks, incidents, decisions and next-month actions.

Quarterly review: pricing, customer concentration, product profitability, reserve target, supplier commitments, tax assumptions and founder salary sustainability.

## 13. Implementation roadmap

### Phase A — Legal and policy foundations
Complete CIPC registration; confirm shareholding, director and beneficial ownership records; open company bank account; appoint accountant/bookkeeping support; agree accounting system of record, chart of accounts and year-end; review pre-incorporation IP; confirm SARS tax profile, VAT strategy and payroll obligations; approve founder remuneration and cash allocation policies.

**Exit:** legal and ownership evidence exists, banking/accounting process is usable and accountant has reviewed initial policies.

### Phase B — Manual finance operations
Set up chart of accounts and cost centres; record opening balances; capture invoices, receipts, expenses and commitments; maintain monthly close checklist and compliance calendar; produce accountant-reviewed monthly pack.

**Exit:** two consecutive monthly closes reconcile to bank and authoritative accounting records without unexplained material differences.

### Phase C — HQ finance foundation
Implement data model, permissions and audit; ingest invoices/receipts/settlements; reconciliation exception queue; expense and supplier workflow; bank statement import/matching without banking credentials; cash buckets, reserve targets and allocation preview.

**Exit:** tests prove invoices, provider settlements, bank deposits, fees, refunds and partial payments reconcile correctly.

### Phase D — Tax, payroll and compliance
Implement obligation calendar and evidence; accountant-reviewed VAT/company-tax workpapers; accountant-approved payroll process; founder salary approval and payslip evidence; CIPC annual-return and beneficial ownership reminders.

**Exit:** accountant signs off assumptions, tax mappings, payroll and evidence workflow before live use.

### Phase E — Forecasting and reporting
Build 30/60/90-day cash forecast; product profitability and shared-cost allocation; subscription-to-cash dashboards; human-reviewed reminders/anomaly alerts; monthly and quarterly packs.

**Exit:** forecasts label assumptions and never present projected cash as actual cash.

## 14. Tests and acceptance criteria

- Invoice without payment: cash collected remains zero.
- Provider payment succeeds but has not settled: pending settlement, not bank cash.
- Provider settles net of fees: gross, fee and net remain traceable.
- Refund/chargeback links to original transaction.
- Duplicate webhook/statement row cannot duplicate posting.
- Partial payment leaves correct receivable balance.
- Inactive VAT registration does not assume authority to charge/claim VAT.
- Historical transactions retain the tax-rule version applicable at the time.
- Non-applicable payroll obligation is marked reviewed/not applicable, not an invented zero payment.
- Salary exceeding affordability triggers warning/block.
- Underfunded reserve is visible and excluded from discretionary cash.
- Unknown bank item remains an exception.
- Closed-period changes require approved adjustment/reopen workflow.
- User without payroll permission is denied and access attempt audited.
- Sensitive export records permission, purpose and audit event.
- Accountant rejection keeps workpaper in review; prepared filing is not marked filed.
- Payment instruction without bank evidence is not marked paid/reconciled.

Operational acceptance requires reconciliation to authoritative books and bank evidence, passing access tests, documented accountant review, verified backup/restore and visible source/freshness for every financial dashboard figure.

## 15. Decisions still to confirm

Final registered name and dates; financial year-end; accounting system of record; accountant/payroll provider; bank/payment provider; VAT strategy based on actual turnover and current SARS rules; founder gross salary and start date based on affordability and payroll advice; reserve account and cash target; approval thresholds and external dual-control; whether HQ owns an accounting subledger or synchronises with the accountant's platform.

**Operating rule:** Saccharum's company account is for company activity. HQ must show what the company owes, what it can spend, what it must reserve, what it has earned and what the founder may lawfully receive—without mixing company money with personal money.
