# Updating LINDA on your own computer

Run these every time you pull new code. Skipping the middle two is the usual
reason for "We couldn't load the dashboard", "We could not create your
account", or funeral screens showing on a business account.

```bash
cd ~/funeral-platform
git checkout main && git pull

cd backend
source venv/bin/activate            # or however you start your Python environment
python3 -m pip install -r requirements.txt
python3 -m alembic upgrade head     # brings the database up to date
python3 -m app.seed_permissions     # brings roles and permissions up to date
# then restart the backend (and the scheduler)

cd ../frontend
npm install
npm run build                       # or npm run dev
```

`alembic: command not found` means the Python environment is not active.
Use `python3 -m alembic ...` as above.

Check it worked: open http://127.0.0.1:8000/health. It should show
`"schema": "current"`. `"out_of_date"` means the database step was skipped.
The backend also logs a warning at start-up when the database is behind.
