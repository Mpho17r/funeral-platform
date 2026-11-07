# LINDA production readiness

This document separates what the repository implements from what must be verified on the live VPS. LINDA is a multi-business platform, not a funeral-only application. Treat customer data, uploaded documents and financial records as production-sensitive.

## 1. Current deployment shape

**Known deployment architecture**
- One VPS runs the Docker Compose deployment.
- Caddy terminates HTTPS for `linda.saccharumtech.co.za` and proxies the web application and `/api` requests.
- The API, frontend, PostgreSQL database and one scheduler process run as separate Compose services.
- PostgreSQL data, uploaded files and local backups use persistent Docker volumes.
- API and frontend ports are bound to localhost behind Caddy; PostgreSQL is internal to the Compose network.
- The scheduler is a single process. Do not run a second copy against the same environment.

**Must be verified on the server**
- Hosting provider account/payment standing and access to the control panel.
- Current deployment commit and image tags.
- Firewall exposes only the intended public HTTP/HTTPS ports.
- Docker services restart after a VPS reboot.
- The current database and uploaded-file volumes are mounted where the application expects them.
- Disk capacity, memory headroom, log rotation and Docker image cleanup are monitored.

## 2. Implemented application controls

| Area | Implemented behaviour | Operational caveat |
| --- | --- | --- |
| Registration | Production registration closes automatically after the first business exists unless `ALLOW_REGISTRATION` explicitly overrides it | Verify the intended public sign-up state; a database containing seed/demo businesses will be closed by default |\n| Authentication | Separate business-user and platform-admin token types; business-user failed-login counts and lockouts are stored on the user record | Platform-admin IP throttling is process-local; it resets on restart and is not shared between workers |
| Permissions | Role permissions plus per-user allow/deny overrides; server-side permission checks | Review permissions whenever new routes/modules are added |
| Tenant separation | Business-owned queries are scoped by business ID; platform admin sees aggregate business/subscription metadata rather than case/member/document contents | Continue regression testing every new endpoint for cross-tenant access |
| Account security | Email verification and password-reset token flows use hashed, expiring, single-use tokens; resend is rate-limited | Email verification is currently not required to sign in (a product decision); token email uses a short-lived background task, not a durable transactional mail queue |
| Operational messaging | Communication messages are queued; configured SMTP email is processed by the scheduler with bounded retries | SMS and WhatsApp require provider integration or manual sending; consent/opt-out rules must be respected |
| Recurring work | One scheduler runs lifecycle, alerts, reminders, message delivery, appointments, stock, archive, overdue, autopilot, usage snapshots and backups | Monitor scheduler heartbeat and job outcomes; a scheduler process being alive does not prove each job succeeded |
| Backups | Database dump and uploaded-file archive are created and locally verified; retention is configured | Local backups are on the same VPS; no automated off-site copy is currently confirmed |
| Health | `GET /health` checks database availability and reports scheduler health | Add an external uptime monitor and alert a human when it fails |
| Pricing | Monthly subscription statements are calculated from usage and VAT settings | This is not recurring payment collection, bank reconciliation or proof that money was received |
| Trial lifecycle | A 30-day trial end timestamp is stored | Trial expiry is not automatically enforced; platform operations must currently change subscription status |
| Uploads | Avatar and branding storage paths are tenant-scoped | File size, decoder and pixel-limit hardening is under review in PR #70; do not assume production includes it until merged and deployed |

## 3. Backups and recovery

The current backup process writes a PostgreSQL dump and an archive of uploaded files to the VPS backup volume. It checks that the database dump is readable and keeps a configured local retention set.

**This is not yet disaster recovery.** Loss, compromise or filesystem failure of the VPS can also destroy the local backup volume.

Before accepting valuable customer data:
- Configure encrypted off-site backup storage with credentials restricted to the backup task.
- Verify the remote object checksum and size after every copy.
- Alert when the newest successful off-site copy exceeds the approved recovery-point objective.
- Define recovery-point objective (RPO) and recovery-time objective (RTO).
- Restore both database and uploaded files into an isolated environment and record the result.
- Repeat restore drills at least quarterly and after major storage/deployment changes.

See [BACKUPS_AND_RECOVERY.md](BACKUPS_AND_RECOVERY.md) for the current backup and restore procedure.

## 4. Security and reliability work still required

1. **Persistent platform-admin throttling.** Move the process-local failed-login counter into a shared persistent store. Store a keyed hash of the client IP, not the raw address; make updates atomic and expire old records.
2. **General API rate limiting.** Add route-aware limits for login, registration, token resend, upload and other abuse-sensitive endpoints.
3. **Durable transactional email.** Verification and password-reset emails should use a persistent queue with retry state, delivery history and secret-safe handling. Do not log raw tokens.
4. **Off-site backups and restore drills.** Local backups alone do not protect against VPS loss.
5. **Image validation.** Fully decode supported formats, enforce byte/dimension/pixel limits and consider metadata stripping/re-encoding. Merge and deploy PR #70 only after CI passes.
6. **Monitoring and alerting.** Add external uptime checks, API error reporting, disk/CPU/memory alerts, backup-age alerts and scheduler-job failure alerts.
7. **Production data review.** Confirm demo/seed businesses and tracked sample assets are not real customer data before using the system for live customers.
8. **Secrets and storage.** Keep environment files out of Git, restrict VPS access, rotate secrets after any exposure and verify disk/volume encryption options with the host.
9. **Trial and billing lifecycle.** Decide the expiry/grace policy and implement payment collection/reconciliation before treating statements as money received.
10. **Tenant isolation regression.** Add cross-business access tests whenever a new module, file route, report or background job is introduced.

## 5. Subscription and financial controls

- The application calculates subscription statements; it does not yet collect recurring payments or reconcile settlements.
- Distinguish invoices/statements, cash received, payment-provider fees, refunds, VAT liability and outstanding balances.
- A trial end date is currently stored but does not automatically suspend access.
- Do not send a payment demand or claim a customer has paid based only on a calculated statement.
- Final LINDA prices must use the separately approved Saccharum commercial strategy. Old repository seed values are not proof of approved prices.
- VAT settings and rates must be reviewed for the relevant legal entity and tax period. This document is not tax or legal advice.

## 6. Privacy and legal readiness (South Africa)

LINDA can hold personal information about customers, family members, staff and business contacts. Depending on the business type, records may include identity, financial, employment and other sensitive operational information. Confirm obligations with a qualified South African privacy/legal professional.

Before live customer onboarding:
- Appoint and register the appropriate Information Officer where required.
- Publish a privacy notice explaining purposes, lawful basis/consent where applicable, retention, rights and contact channels.
- Put an operator/data-processing agreement in place with hosting and other service providers.
- Document retention, deletion, export and backup-retention policies.
- Maintain a breach-response plan and know who must be notified and when.
- Obtain and record appropriate channel consent before marketing or operational messaging.
- Restrict support access to customer data and audit exceptional access.
- Treat exports and backups with the same protection as the live database.

## 7. First-customer go-live checklist

- [ ] Confirm the live deployment is on the reviewed commit and the latest approved image.
- [ ] Confirm HTTPS, DNS, Caddy routing and firewall rules.
- [ ] Confirm production secrets are strong, private and not present in Git.
- [ ] Confirm database and upload volumes survive container recreation and VPS reboot.
- [ ] Confirm only one scheduler is running and its heartbeat is current.
- [ ] Send and receive a real test email; verify delivery failures are visible.
- [ ] Verify `ALLOW_REGISTRATION` and the public registration status endpoint; create a customer through the intended onboarding path without accidentally opening owner setup.
- [ ] Verify tenant isolation with two separate test businesses.
- [ ] Verify role permissions and platform-admin separation.
- [ ] Verify upload limits, image validation and storage persistence after PR #70 is deployed.
- [ ] Complete an off-site backup and restore drill.
- [ ] Confirm support contact, incident owner and recovery instructions.
- [ ] Confirm customer terms, privacy notice, operator agreement and tax treatment.
- [ ] Confirm final prices, plan limits, trial policy and payment terms before charging customers.

## 8. Day-to-day operations

- Check `/health` from an external monitor.
- Review scheduler heartbeat and failed job details.
- Review local and off-site backup freshness.
- Monitor disk usage, database capacity, memory and container restarts.
- Review platform-admin sign-in failures and privileged audit events.
- Review queued/failed emails and customer support messages.
- Keep a release log with commit, migration, deployment time and rollback reference.
- Perform a restore drill quarterly; a backup nobody has restored is only an assumption.
