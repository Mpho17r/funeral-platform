# Saccharum HQ metric dictionary

This document defines the numbers shown on HQ dashboards. A metric must never be displayed without its period, source, currency (where relevant), and last-refresh time.

## Finance

| Metric | Definition | Source / control |
| --- | --- | --- |
| Monthly recurring revenue (MRR) | Monthly value of active recurring subscriptions, excluding VAT, one-off onboarding, migration, training and bespoke services | Subscription ledger; exclude trials, cancelled accounts and non-recurring charges |
| Annual recurring revenue (ARR) | MRR multiplied by 12, shown as a run-rate rather than cash received | Derived from MRR; label as annualised run-rate |
| Invoiced revenue | Approved invoice line totals excluding VAT for the selected period | Invoice ledger, net of credit notes |
| Cash collected | Customer payments confirmed as settled/received for the period | Payment and bank reconciliation records; never infer from invoices or statements |
| Provider fees | Fees charged by the payment provider on transactions | Provider settlement records |
| Net settlements | Cash settled by the provider after fees, refunds and chargebacks | Settlement reconciliation |
| Accounts receivable | Open invoice balances not yet paid or credited | Invoice ledger and receipt allocations |
| Refunds and credits | Approved refunds and credit notes for the selected period | Immutable refund/credit records with approver |
| Operating expenses | Approved expenses recognised in the selected accounting period | Expense ledger/accounting integration |
| Net cash movement | Cash received minus cash paid in the period | Reconciled bank/cash transactions, not invoice totals |
| Cash runway | Unrestricted available cash divided by average monthly net cash burn over an agreed lookback period | Bank balances and cash-flow ledger; show lookback window and assumptions |
| Gross margin | Revenue excluding VAT less directly attributable cost of service | Accounting policy and cost allocation approved by accountant |

## Tax and compliance

| Metric | Definition | Important caveat |
| --- | --- | --- |
| Output VAT | VAT charged on taxable sales in the relevant tax period | Apply the correct tax point, rate and treatment for each transaction |
| Recoverable input VAT | VAT on eligible business purchases supported by valid evidence | Not every expense VAT amount is recoverable |
| Estimated VAT payable/refund | Output VAT less eligible input VAT, adjusted for credit notes and relevant corrections | Must be reviewed against the entity's tax profile and accountant-approved records |
| Tax obligation due | Amount and deadline associated with a specific obligation and tax period | A calendar reminder is not proof of filing or payment |
| Filing status | Draft, under review, filed, accepted/rejected or amended | Keep submission reference and supporting evidence |
| Payment status | Unpaid, scheduled, paid or reconciled | Mark paid only when supported by bank/SARS/provider evidence |

HQ must not calculate a statutory liability from subscription invoices alone. VAT treatment, tax periods, deductions and filing rules require an accountant-approved policy and current authoritative tax guidance.

## Customers and subscriptions

| Metric | Definition |
| --- | --- |
| Registered accounts | Distinct customer accounts created in the selected period |
| Active customers | Distinct customer accounts with at least one active product subscription |
| Paying customers | Distinct customer accounts with a paid/settled subscription charge in the selected period or a current paid entitlement |
| Trial accounts | Distinct accounts currently in a trial state |
| Trial conversion rate | Trials in a defined cohort that become paid subscriptions divided by eligible trials in that cohort |
| Logo churn | Customer accounts cancelled during the period divided by paid customer accounts at the start of the period |
| Gross revenue churn | Recurring revenue lost from cancellations and downgrades divided by opening MRR |
| Net revenue retention | Opening cohort recurring revenue plus expansion, less contraction and churn, divided by opening cohort recurring revenue |
| Activation rate | New accounts that complete the agreed activation milestone within the defined window |
| Usage | Product-defined active users, branches, members, cases or other meaningful activity; always state the counting rule |

Use cohort-based conversion and churn metrics. Do not divide by an unstable denominator or compare partial periods without labelling them.

## Platform reliability

| Metric | Definition |
| --- | --- |
| Availability | Successful external health checks divided by all valid checks in the selected period |
| API error rate | Failed API requests divided by total API requests, segmented by route/status class |
| Latency | p50, p95 and p99 response times; never show an average alone |
| Background-job success | Successful job executions divided by attempted executions, with failed job names and age |
| Queue age | Age of the oldest pending outbound message or integration event |
| Backup age | Time since the latest verified local backup |
| Off-site backup age | Time since the latest checksum-verified remote backup |
| Restore confidence | Date and result of the latest successful isolated restore drill, with measured recovery time |
| Release health | Current release version, migration state, deployment time and post-deploy health checks |

Availability is not the same as the scheduler being alive. A green process heartbeat must not hide failed background jobs.

## Support and feedback

- **First response time:** time from customer submission to first human or approved automated response; show median and p90.
- **Resolution time:** time from ticket creation to confirmed resolution; separate open tickets from resolved ones.
- **SLA attainment:** tickets meeting the response/resolution target divided by tickets due in the period.
- **Backlog:** open items by age, priority, product and owner.
- **Feedback themes:** count of tagged feedback items by theme; sentiment is a qualitative signal, not a financial metric.

## Display and data-quality rules

1. Show the reporting period and timezone for every time-based metric.
2. Show ZAR and whether values include or exclude VAT.
3. Separate actuals, forecasts, estimates and targets visually and textually.
4. Show the source system and last refreshed timestamp.
5. Flag stale, incomplete or unreconciled data; never silently replace missing values with zero.
6. Provide a drill-through to the source records and audit history for financial, tax and subscription figures.
7. Use consistent definitions across dashboard cards, reports, exports and alerts.
8. Keep a versioned metric definition when the calculation changes, so historical reports remain explainable.
