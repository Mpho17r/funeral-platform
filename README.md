# FuneralOS

FuneralOS is a multi-tenant operating system for funeral businesses. The GitHub repository is the implementation source of truth; the project blueprint and tracker capture agreed architecture, current evidence, and the next work.

## Project documentation

- [Product blueprint and system structure](docs/FUNERALOS_BLUEPRINT.md) — product principles, business/branch structure, case journey, department workspaces, security invariants, and roadmap.
- [Production readiness](docs/PRODUCTION_READINESS.md) — hosting options, safe settings, setup recipe, launch checklist and POPIA notes.
- [Backups and recovery](docs/BACKUPS_AND_RECOVERY.md) — nightly backups, restore drill and the owner's data export.
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
