# FuneralOS Product Blueprint and System Structure

**Last reviewed:** 2026-10-19  
**Repository:** [Mpho17r/funeral-platform](https://github.com/Mpho17r/funeral-platform)  
**Baseline branch:** `main`  
**Baseline commit:** [d3457e6 — merge automatic case lifecycle](https://github.com/Mpho17r/funeral-platform/commit/d3457e6eb24eaafa2cba4fb4c2b8aec7dace4d63)

> This is the working product and architecture blueprint. It separates verified implementation from target design and open reviews. Code on GitHub is the source of truth for implementation status; this document is the source of truth for agreed direction until superseded by a reviewed change.

## 1. Product direction

FuneralOS is a multi-tenant operating system for funeral businesses. It should connect the work from first case registration through custody, preparation, funeral arrangements, service delivery, finance, membership/cover, and final closure around one canonical case record.

The system must support small funeral homes that combine several departments and larger businesses that have multiple branches, dedicated teams, and shared facilities.

### Non-negotiable principles

1. **Tenant isolation:** each funeral business can access only its own records. A platform-level Saccharum Technologies operator role is separate from a funeral business's Main Admin.
2. **Branch-aware access:** businesses may have multiple branches. Business owners/Main Admins can oversee authorised business-wide data; branch-scoped employees see only the branches and work items their permissions allow.
3. **One case record:** operational stages update the same case and linked records. Staff must not recreate cases or re-enter information at every stage.
4. **Permission enforcement is server-side:** hiding a page or dashboard tile is not security. API routes, services, and database queries must enforce business, branch, and permission boundaries.
5. **Human confirmation for physical work:** automation may calculate, schedule, queue, notify, or suggest next steps. It must not claim a body was collected, identified, cooled, prepared, released, or a funeral occurred unless an authorised person records the required evidence.
6. **Auditable changes:** sensitive changes, custody events, approvals, transfers, financial operations, and status transitions must leave a trace.
7. **Preserve history:** deactivate/archive records where appropriate rather than deleting operational history. Permanent deletion is a separately controlled operation.
8. **Build from existing code:** inspect the default GitHub branch, migrations, tests, and recent commits before asking for local inspection or implementing duplicate functionality.

## 2. Current verified implementation baseline

The following items were found in the GitHub `main` branch during the 2026-10-19 review. This is a repository review, not a claim that production deployment or every end-to-end scenario has been independently tested.

### Platform and engineering

- Backend: Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL.
- Frontend: Next.js / React / TypeScript.
- CI workflow: `.github/workflows/ci.yml` runs database migrations, permission seeding, backend tests, TypeScript checking, and a frontend production build.
- Main database migration check in CI requires a single Alembic head.
- Permission setup is synchronised through `python -m app.seed_permissions`.

### Business, branches, and resources

- `Business` stores business identity, branding/theme preferences, membership-cover policy, reminder configuration, attendance/break policy, contact details, and active status.
- `Branch` is a business-owned location. The model enforces unique branch codes and case-insensitive names per business, one main branch per business, and an active main branch.
- Branch services support creating the main branch, resolving a default branch, assigning records to an active branch of the same business, moving supported records, counting live cases, and preventing deactivation of a main branch or a branch with live cases.
- Branch API operations use permissions and write audit records.
- The current `MortuaryLocation` model is a business-owned place (fridge, cold room, preparation room, chapel of rest, or other) with an optional single `branch_id`, capacity, and active status.
- The current mortuary data model includes a `RemainsRecord` linked uniquely to a case, plus custody events and controls for intake, location, identification, cooling, and release. See the mortuary API and tests for exact implemented behaviour.

### Cases and arrangements

- The existing audited case lifecycle service validates status transitions.
- The merged automatic lifecycle implementation synchronises a case with its linked funeral arrangement:
  - confirming an arrangement can confirm an open case;
  - after the confirmed committal time, a case can become in progress;
  - completion requires the arrangement itself to be recorded as completed and the committal time to have passed;
  - draft/cancelled arrangements and archived/terminal cases do not auto-advance;
  - every status transition uses the audited lifecycle service.
- A one-shot job is available at `python -m app.jobs.sync_case_lifecycle`. Production scheduling is an operational deployment responsibility and must be configured deliberately.
- This arrangement-driven status synchronisation is **not** a replacement for the proposed detailed operational checklist for collection, mortuary intake, preparation, release, transport, and family handover. Those physical tasks require their own evidence and authorised confirmation.

### Other capabilities evidenced in the repository history

- Staff workspace chat and channels, with a follow-up phase for meetings, calls, reactions, mentions, and file sharing: [PR #11](https://github.com/Mpho17r/funeral-platform/pull/11), [PR #12](https://github.com/Mpho17r/funeral-platform/pull/12).
- Automatic daily reminder queueing is designed so that queued reminders still wait for a person to send them: [PR #10](https://github.com/Mpho17r/funeral-platform/pull/10).
- Owner reporting includes period comparisons, trends, and CSV exports: [PR #9](https://github.com/Mpho17r/funeral-platform/pull/9).
- Onboarding includes business details and data-import flows for payment history, cases, dependants, and beneficiaries: [PR #4](https://github.com/Mpho17r/funeral-platform/pull/4), [PR #5](https://github.com/Mpho17r/funeral-platform/pull/5), [PR #6](https://github.com/Mpho17r/funeral-platform/pull/6), [PR #7](https://github.com/Mpho17r/funeral-platform/pull/7).
- These PR references document repository history; verify the current code and tests before treating a specific behaviour as production-ready.

## 3. Target business structure

The intended ownership and access hierarchy is:

```text
Saccharum Technologies (platform owner / platform administration)
└── FuneralOS platform control plane
    ├── business subscriptions and platform usage (future platform module)
    └── Funeral business tenant
        ├── Main Admin / business owner
        ├── Branch A
        │   ├── staff and department assignments
        │   ├── cases, members, resources, and branch operations
        │   └── branch dashboard and permitted reports
        ├── Branch B
        │   └── its own branch-scoped records and operations
        └── shared business resources / shared facilities (target design)
```

**Important boundary:** Saccharum platform administration is not the funeral business Main Admin. A business Main Admin manages only their own business. A user working on a case in another branch must not automatically receive access to that branch's unrelated financial, membership, HR, or other sensitive data.

### Shared mortuary requirement — planned, not yet verified as implemented

A mortuary may serve one branch or several branches. The current location record has one optional `branch_id`; that alone does not model a facility explicitly shared by multiple branches. Before implementing sharing, inspect the full resource and branch-access design and decide whether to introduce a first-class mortuary/facility entity with an explicit many-to-many branch association, or an equivalent clear model.

The design must preserve:
- one owning business/tenant for each facility;
- explicit branches authorised to use it;
- case-specific access to work assigned to that facility;
- capacity and occupancy enforcement across all authorised branches;
- custody and movement history;
- no cross-business facility sharing;
- no implied access to unrelated branch records.

## 4. Canonical case journey — target operational blueprint

The case is the central record. The exact path can vary by service, but each required step must be visible, assignable, timestamped, and auditable.

1. **Registration and verification** — create the case once; record identity, next of kin/family contacts, required documents, authorisations, service type, and initial branch.
2. **Collection / dispatch** — assign collection task, authorised staff, vehicle/resource, pickup location, time, and required paperwork. Completion requires staff confirmation and relevant details.
3. **Mortuary intake and identification** — record receipt time, source, tag number, condition/belongings where applicable, responsible staff, identification checks, and custody event.
4. **Cooling and storage** — assign an approved cold location, enforce capacity, record cooling time and movements, and surface overdue cooling or missing-location issues.
5. **Preparation** — assign approved preparation tasks (for example washing, embalming where applicable, dressing), responsible staff, timestamps, notes, and any required checks.
6. **Readiness and paperwork** — track service readiness and required documents/authorisations. A checklist being complete must not imply an unperformed physical task.
7. **Release / transfer / viewing / memorial / funeral** — support only the stages relevant to the case. Release requires the configured paperwork, identity/tag confirmation, authorised recipient, and recorded approval. Transfers require destination and custody handover.
8. **Final closure** — verify the required operational, paperwork, and financial or administrative conditions defined by business policy; record who closed the case and when.

### Workflow behaviour

- Each stage should display its next required action, owner/assignee, due time, blockers, and evidence.
- Completing a stage should make the next applicable action available; it should not silently complete that action.
- Reassignment, branch transfer, mortuary movement, release, cancellation, and closure must retain history.
- A case can follow a different valid route (for example repatriation/transfer or cremation) without inventing irrelevant tasks.
- Statuses on the case are useful summaries, not substitutes for the detailed task and custody records.

## 5. Department and dashboard blueprint

Dashboards are role- and assignment-specific workspaces. A small business may combine these responsibilities; larger businesses can separate them.

| Workspace / department | Main work surface |
|---|---|
| Business owner / Main Admin | Business-wide overview across authorised branches, operational blockers, permitted financial summaries, staffing and reports |
| Branch manager | Branch cases, staff, resources, schedules, and branch reports |
| Operations coordinator | Case pipeline, next actions, assignments, due dates, dependencies, and blockers |
| Case registration / administration | New cases, family details, documents, verification, approvals, and intake handoff |
| Mortuary | Intake queue, custody, tag/identity checks, cold-room occupancy, cooling deadlines, preparation, readiness, and release |
| Transport / dispatch | Collections, transfers, vehicles, drivers, route/delivery tasks, and handover confirmation |
| Funeral arrangements / service operations | Service details, venue, dates, suppliers, readiness, and funeral-day coordination |
| Finance / accounts | Invoices, receipts, payments, expenses, balances, credits, and financial reports |
| Membership / cover / benefits | Members, dependants, contribution history, arrears, cover status, claims and benefits |
| Family liaison / customer service | Approved family contacts, communication history, preferences, arrangements, and outstanding requests |
| Compliance / documentation / quality | Required records, permits, approvals, custody evidence, audit review, and exceptions |
| HR / staff management | Staff assignments, shifts, attendance, breaks, and leave/schedule context |
| Procurement / stock / facilities | Coffins, consumables, PPE, stock levels, equipment, maintenance, and facility readiness |
| Platform administration (Saccharum) | Cross-tenant subscription/usage and platform health only through a separately authorised platform-level control plane; planned scope must not be exposed to business admins |

Do not expose financial totals just because a user can view a general dashboard. Use dedicated financial permissions and branch/tenant-scoped queries for financial data. Do not expose membership or HR details merely because a user can see a case.

## 6. Security and data-access invariants

- Derive the business/tenant scope from the authenticated identity; never trust a client-supplied business ID as authorisation.
- Validate every referenced case, branch, facility, member, resource, and user against the current business.
- Apply branch scope in backend queries and mutation checks, not only in navigation or UI filters.
- Keep role permissions and per-user overrides centralised. The current permission service documents the rule: explicit user deny overrides user allow/role; explicit user allow overrides role; otherwise role permission applies; default is deny. Main Admin permissions must still remain inside their own business tenant.
- Separate general dashboard access from finance, membership, HR, compliance, and platform-administration access.
- Apply least privilege and default-deny behaviour.
- Audit access-sensitive mutations and status changes. Keep custody events append-only in normal workflows.
- Use tests for cross-tenant access, cross-branch access, explicit denies, and privilege boundaries, including API responses that could leak aggregate totals.
- Do not treat a passing build as proof of access-control correctness.

## 7. Architecture map

Current repository paths confirmed during review:

- `backend/app/models/` — SQLAlchemy domain models, including business, branch, case, and mortuary records.
- `backend/app/api/` — FastAPI routes, including branches and mortuary.
- `backend/app/services/` — business rules such as branch assignment, permission checks, and case lifecycle transitions.
- `backend/app/dependencies/` — request dependencies such as permission enforcement.
- `backend/app/schemas/` — API request/response contracts.
- `backend/app/jobs/` — one-shot scheduled tasks, including case-lifecycle synchronisation.
- `backend/tests/` — backend API/service tests.
- `backend/alembic/` or the configured migrations directory — schema evolution; confirm the exact path in the repo when working on migrations.
- `frontend/app/`, `frontend/lib/` — Next.js screens and shared client utilities.
- `.github/workflows/ci.yml` — automated backend and frontend checks.

Keep domain rules in services where they can be reused by APIs and jobs. API routes should authenticate, authorise, validate input, call the service, and return a bounded response.

## 8. Prioritised work queue

### P0 — security and scope review

- [ ] Review the dashboard summary permission boundary. The current `backend/app/api/dashboard.py` endpoint is guarded by `dashboard.view` and its query includes business-wide financial aggregates. Confirm the seeded role grants and tests; if general dashboard viewers can see these values, split financial visibility into a dedicated permission and add tests.
- [ ] Audit branch-scoped access across cases, members, staff, resources, finance, reports, and mortuary routes. Ensure business ownership and user branch access are enforced in every relevant query and mutation.
- [ ] Add or confirm cross-tenant and cross-branch negative tests for dashboard aggregates and linked records.

### P1 — operational blueprint

- [ ] Map the current case, arrangement, remains/custody, paperwork, resource, and task models to the end-to-end journey in Section 4.
- [ ] Identify which journey steps already exist and which need new records, permissions, API routes, UI, and tests before writing new code.
- [ ] Define task assignment, blockers, handoffs, and human-confirmation requirements for physical operations.

### P2 — shared facilities and cross-branch operations

- [ ] Design shared mortuary/facility ownership and explicit branch authorisation.
- [ ] Define capacity and custody rules when a case moves between branches or facilities.
- [ ] Add migration, service/API changes, UI, and multi-branch tests only after the model is agreed.

### P3 — role-specific dashboards

- [ ] Map each department workspace to existing pages, API endpoints, and permission keys.
- [ ] Separate dashboard presentation from backend authorisation.
- [ ] Test each role with both allowed and denied access cases.

### P4 — platform owner and commercial controls

- [ ] Keep Saccharum's platform administration separate from tenant administration.
- [ ] In a later phase, define subscriptions, enabled features, branches/users/members/cases/storage limits, usage metrics, and overage monitoring.
- [ ] Do not introduce billing/limits until tenant and permission boundaries are reliable.

## 9. Working protocol for future sessions

1. Start from GitHub `main` and recent commits, unless the user explicitly chooses another branch.
2. Check the relevant existing files, migrations, tests, and PR history before requesting terminal output.
3. Label findings **Implemented**, **Needs verification**, or **Planned**.
4. Make the smallest coherent change; avoid duplicating an existing model/service/permission.
5. Add/update tests with backend behaviour changes, especially for access control and workflow transitions.
6. Update this blueprint and the project tracker whenever architecture, scope, or implementation status changes.
7. Run GitHub Actions when available; use local commands only when a local environment-specific check is required.
8. Never report a change as deployed, tested, or saved unless the relevant tool/result confirms it.

## 10. Source links

- [Repository](https://github.com/Mpho17r/funeral-platform)
- [CI workflow](https://github.com/Mpho17r/funeral-platform/blob/main/.github/workflows/ci.yml)
- [Branch model](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/models/branch.py)
- [Branch service](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/services/branch_service.py)
- [Mortuary model](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/models/mortuary.py)
- [Mortuary API](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/api/mortuary.py)
- [Automatic case lifecycle service](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/services/automatic_case_lifecycle.py)
- [Scheduled lifecycle job](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/jobs/sync_case_lifecycle.py)
- [Dashboard summary API](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/api/dashboard.py)
- [Automatic lifecycle PR #13](https://github.com/Mpho17r/funeral-platform/pull/13)
