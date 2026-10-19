# FuneralOS Project Tracker

**Last updated:** 2026-10-19  
**Source of truth for code:** GitHub `main` and its tests/migrations  
**Blueprint:** [FUNERALOS_BLUEPRINT.md](./FUNERALOS_BLUEPRINT.md)

This tracker records verified repository evidence and the next agreed work. Status is intentionally conservative: a merged PR or present file is evidence of implementation, but not by itself proof of production deployment or complete operational readiness.

## Latest confirmed repository baseline

- Default branch: `main`
- Reviewed baseline commit: [d3457e6](https://github.com/Mpho17r/funeral-platform/commit/d3457e6eb24eaafa2cba4fb4c2b8aec7dace4d63)
- Latest reviewed merge: [PR #13 — Automatically advance funeral case lifecycle from arrangements](https://github.com/Mpho17r/funeral-platform/pull/13)
- CI definition: [`.github/workflows/ci.yml`](https://github.com/Mpho17r/funeral-platform/blob/main/.github/workflows/ci.yml)

## Implementation inventory

| Area | Status | Evidence / notes |
|---|---|---|
| Business tenant and branding/policy settings | Implemented in repository | [Business model](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/models/business.py) |
| Multiple branches and one protected main branch per business | Implemented in repository | [Branch model](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/models/branch.py), [branch service](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/services/branch_service.py) |
| Branch create/read/update/deactivate flows with permission checks and auditing | Implemented in repository; review access scope as part of security pass | [Branch API](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/api/branches.py) |
| Mortuary locations, remains custody record, custody events, cooling/identification/release rules | Implemented in repository; verify complete journey against blueprint | [Mortuary model](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/models/mortuary.py), [API](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/api/mortuary.py), [tests](https://github.com/Mpho17r/funeral-platform/blob/main/backend/tests/test_mortuary.py) |
| Arrangement-driven case status synchronisation | Implemented in repository; do not confuse case status with physical task completion | [Lifecycle service](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/services/automatic_case_lifecycle.py), [job](https://github.com/Mpho17r/funeral-platform/blob/main/backend/app/jobs/sync_case_lifecycle.py), [PR #13](https://github.com/Mpho17r/funeral-platform/pull/13) |
| Staff chat/channels and meetings/calls/reactions/mentions/file sharing | Present in merged repository history; validate against current routes/tests when changing | [PR #11](https://github.com/Mpho17r/funeral-platform/pull/11), [PR #12](https://github.com/Mpho17r/funeral-platform/pull/12) |
| Automatic reminder queue | Present in merged repository history; queued reminders still require human send action | [PR #10](https://github.com/Mpho17r/funeral-platform/pull/10) |
| Owner reporting and formula-safe CSV exports | Present in merged repository history; review role/branch access for exports | [PR #9](https://github.com/Mpho17r/funeral-platform/pull/9) |
| Onboarding and imports for payment history, cases, dependants, beneficiaries | Present in merged repository history; inspect exact paths before extending | [PR #4](https://github.com/Mpho17r/funeral-platform/pull/4), [PR #5](https://github.com/Mpho17r/funeral-platform/pull/5), [PR #6](https://github.com/Mpho17r/funeral-platform/pull/6), [PR #7](https://github.com/Mpho17r/funeral-platform/pull/7) |
| GitHub Actions backend migrations/tests and frontend type-check/build | Workflow configured; latest run result not checked in this review | [CI workflow](https://github.com/Mpho17r/funeral-platform/blob/main/.github/workflows/ci.yml) |

## Open reviews and additions

| Priority | Status | Item | Acceptance condition |
|---|---|---|---|
| P0 | Needs review | Dashboard financial exposure | General `dashboard.view` does not expose finance totals unless the user also has explicit finance permission; add allow/deny and branch-scope tests |
| P0 | Needs review | Tenant and branch isolation | Every relevant API query and mutation enforces tenant scope and assigned branch access; cross-tenant and cross-branch tests pass |
| P1 | Blueprint agreed; implementation mapping needed | One case, end-to-end operational journey | Each required stage has a record, assignee, evidence, timestamp, blocker/next action, and audit trail; no duplicate case or manual re-entry |
| P1 | Planned | Department-specific workspaces | Navigation, data, actions, and dashboard summaries match role/department permissions; API remains the security boundary |
| P2 | Planned | Shared mortuary across branches | Facility has explicit authorised branch links and tenant ownership; capacity, custody, and movement remain consistent across branches |
| P2 | Planned | Operational tasks and handoffs | Completing a step exposes the next applicable action without auto-confirming physical work |
| P3 | Future scope | Saccharum platform-owner control plane | Separate cross-tenant subscription and usage administration; no privilege bleed into tenant Main Admin |
| P3 | Future scope | Subscription and usage limits | Branch/user/member/case/storage/feature limits and overage metrics defined after tenant isolation is reliable |

## Next session starting point

1. Review the `dashboard.view` role grants and dashboard tests in GitHub; split finance permission if required.
2. Trace branch-scoped access in the case, member, staff, resource, finance, report, and mortuary APIs.
3. Map existing case/arrangement/remains/paperwork/resources to the operational journey before adding duplicate structures.
4. Design the shared mortuary relationship after inspecting the existing facility/resource model and migrations.
5. Update this tracker and the blueprint after each meaningful code change or architectural decision.

## Session rules

- Prefer GitHub code and PR review over repeated terminal inspection.
- Do not assume local branch contents match `main`.
- Do not apply or drop saved Git stashes without a clear need and explicit user direction.
- Keep implemented, verified, planned, and production-deployed statuses separate.
- When a feature changes, update tests and this tracker together.
