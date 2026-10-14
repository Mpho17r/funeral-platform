
## Running without your own computer

### Check every push (GitHub Actions)

`.github/workflows/ci.yml` runs on every push and pull request. It starts a
temporary Postgres, then runs `alembic upgrade head`,
`python -m app.seed_permissions`, the backend tests, `npx tsc --noEmit` and
`npm run build`. Open the **Actions** tab (or the checks on a pull request) to
see the result. The database is discarded afterwards, so this is a check, not
a place to use the app.

### Use the app in the browser (GitHub Codespaces)

1. On the repository page choose **Code → Codespaces → Create codespace** on
   the branch you want.
2. Wait for the first setup to finish. It installs everything, creates the
   database, runs `alembic upgrade head` and `python -m app.seed_permissions`,
   and starts the API and the app.
3. Open the forwarded port **3000** (the **Ports** tab) to use the app. Register
   a business on the login page to get started.

Logs are in `/tmp/funeralos/api.log` and `/tmp/funeralos/web.log`. To run a
step by hand in the Codespace terminal:

```bash
cd backend && alembic upgrade head
cd backend && python -m app.seed_permissions
cd frontend && npm run build
```

After pulling new code that adds migrations or permissions, run the first two
commands again and restart the API with `bash .devcontainer/start.sh`.
