# FuneralOS Project Tracker

**Last updated:** 2026-10-25
**Source of truth for code:** GitHub `main`, its tests and migrations
**Blueprint:** [FUNERALOS_MASTER_BLUEPRINT.md](./FUNERALOS_MASTER_BLUEPRINT.md)

Status is conservative: "built and tested" means merged to `main` with CI green. It does not mean deployed, and nothing here has run with real customer data yet.

## Built and tested

| Area | Notes |
|---|---|
| Tenancy, branches, roles, per-user permission overrides | Main branch protected; work-area roles (mortuary, finance, operations) |
| **Branch isolation** (#29) | Branch-limited staff only see their branch's records, enforced centrally on every read; `branches.all_access` lifts it; cross-branch writes refused |
| Cases, families, contacts, documents, tasks, paperwork, death records | Case is the spine |
| Arrangements and automatic case lifecycle | Case status follows arrangements; physical work is never auto-confirmed |
| Mortuary: custody, locations, cooling alerts, hygiene, belongings, viewings | See [MORTUARY_PRACTICE_REVIEW.md](./MORTUARY_PRACTICE_REVIEW.md) |
| **Shared mortuary** (#31) | A location hosted by one branch can be shared with others; host sees remains kept in it |
| Membership, plans, contributions, payments, claims, waiting periods | Status and coverage engines kept separate |
| Finance: quotes/invoices/receipts, expenses, reconciliation | |
| Resources, bookings, inventory, suppliers, run sheet | |
| Staff chat, meetings, automatic organisation and branch groups | |
| Global search, in-app notifications, licences register | |
| Reports and CSV export; whole-business data export; nightly backups | See [BACKUPS_AND_RECOVERY.md](./BACKUPS_AND_RECOVERY.md) |
| Production readiness: settings checks, scheduler, honest health check, closed sign-up | See [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md) |
| **Message delivery** (#32) | Email sent automatically over SMTP; WhatsApp/SMS remain one-tap manual | [MESSAGE_DELIVERY.md](./MESSAGE_DELIVERY.md) |
| **Family and member portals** (#33) | Private, expiring, revocable links; no accounts |
| **Platform admin, plan limits, Ask FuneralOS** (#34) | Separate operator login; limits enforced on save | [PLATFORM_ADMIN.md](./PLATFORM_ADMIN.md) |
| **KAI assistant** | Greeting, branch/role context, conversation memory, case gaps, confirmed actions | [KAI.md](./KAI.md) |
| **Tasks overhaul** | Assignees update status, shared tasks, reports and files, due date/time grouping, My/Branch/Organisation views, sign-in alert, own-schedule calendar, voice call and alert tones | — |

## Known gaps (honest list)

| Priority | Gap |
|---|---|
| Before real customers | **Not hosted yet.** Local Mac only; decision pending (South African VPS recommended in PRODUCTION_READINESS.md). Public portal links need a reachable address. |
| Before real customers | Uploaded files are not encrypted at rest; no API rate limiting beyond sign-in lockout and portal guessing; no error reporting/monitoring service. |
| Before real customers | Run a real restore drill from a backup on the target server. |
| Product | WhatsApp and SMS are not sent automatically (needs a provider account). |
| Product | Operational hand-offs: completing a step does not yet surface the next action automatically. |
| Product | Portals are read-only: no signatures, approvals, document downloads or family messaging. Member portal does not take payments. |
| Product | Expired trials are not locked automatically (operator moves them by hand). No billing or invoicing of subscriptions. |
| Mortuary | Post-mortem/forensic status tracking, fingerprinting of unidentified remains and preparation-room temperature limit are not built. |
| Product | "Ask FuneralOS" answers a fixed set of questions; it is not a free-form AI. |
| Quality | Browser checks were done by hand on key screens; there is no automated end-to-end browser suite in CI. |

## After each merge on your own computer
`git pull`, then `alembic upgrade head` and `python -m app.seed_permissions` (from `backend/`), and restart the servers.

## Next
1. Decide hosting and deploy (see PRODUCTION_READINESS.md).
2. Pilot with one real funeral parlour on real (migrated) data; fix what real use shows.
3. Pick from the gaps above based on what the pilot needs first.

## Working rules
- Branch, PR, CI green, merge. Update this tracker and tests together with the feature.
- Keep built, deployed and planned separate; never claim deployment without evidence.

## Stock automation (added 2026-10-26)
A service line linked to a stocked item issues the stock to the case by itself and gives it back if the line is cancelled or deleted. Running low alerts the people who manage stock once; an item can also order itself from its supplier (emailed when email is set up, otherwise left as "needs sending"). One open order per item; receiving stock closes it.
