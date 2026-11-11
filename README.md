# LINDA

LINDA (Linked Intelligence for Networked Development & Administration) is a multi-tenant, multi-industry business management platform, owned by Saccharum Technologies. It began with funeral businesses and now also serves general businesses. The GitHub repository is the implementation source of truth; the project blueprint and tracker capture agreed architecture, current evidence, and the next work.

## Project documentation

- [LINDA product blueprint and system structure](docs/FUNERALOS_BLUEPRINT.md) — original product foundation, business/branch structure, operational workflows, security invariants and roadmap.
- [Production readiness](docs/PRODUCTION_READINESS.md) — current VPS deployment shape, implemented controls, real launch gaps and first-customer checklist.
- [Backups and recovery](docs/BACKUPS_AND_RECOVERY.md) — database and upload backups, restore drill and the owner's data export.
- [Saccharum HQ architecture](docs/SACCHARUM_HQ_ARCHITECTURE.md) — owner operations command centre, integration boundaries, data model, security and phased build plan.
- [Saccharum HQ metric dictionary](docs/SACCHARUM_HQ_METRIC_DICTIONARY.md) — definitions for MRR/ARR, cash collected, VAT obligations, customer health, platform reliability and support metrics.
- [Project tracker](docs/PROJECT_TRACKER.md) — what is present in the repository, what needs review, and the next priorities.

## Running without your own computer

### Check every push (GitHub Actions)

`.github/workflows/ci.yml` runs on every push and pull request. It starts a
temporary Postgres, then runs `alembic upgrade head`,
`python -m app.seed_permissions`, the backend tests, `npx tsc --noEmit` and
`npm run build`. Open the **Actions** tab (or the checks on a pull request)
to see the result. The database is discarded afterwards, so this is a check,
not a place to use the app.

### Use the app in the browser (GitHub Codespaces)

1. On the repository page choose **Code → Codespaces → Create codespace** on
   the branch you want.
2. Wait for the first setup to finish. It installs everything, creates the
   database, runs `alembic upgrade head` and `python -m app.seed_permissions`,
   and starts the API and the app.
3. Open the forwarded port **3000** (the **Ports** tab) to use the app. Create
   your first business and administrator with
   `cd backend && python -m app.create_owner`.

Logs are in `/tmp/funeralos/api.log` and `/tmp/funeralos/web.log`. To run a
step by hand in the Codespace terminal:

```bash
cd backend && alembic upgrade head
cd backend && python -m app.seed_permissions
cd frontend && npm run build
```

After pulling new code that adds migrations or permissions, run the first two
commands again and restart the API with `bash .devcontainer/start.sh`.
