# Automatic funeral case lifecycle

FuneralOS uses the linked funeral arrangement to keep case status progressing
through the audited chain:

- `open → confirmed` when a funeral arrangement is confirmed.
- `confirmed → in_progress` when the confirmed committal time has passed.
- `in_progress → completed` when the arrangement has been recorded as completed
  and the committal time has passed.
- `completed → closed` remains a separate administrative close-out action.

The case and arrangement remain separate records and have their own statuses.
Draft/cancelled arrangements do not advance a case. Cancelled, closed, completed,
and archived cases are not automatically changed. Every case transition is
written to the audit log.

## Schedule the automatic date check

From the deployed backend environment, run:

```bash
python -m app.jobs.sync_case_lifecycle
```

Configure the hosting provider's scheduled-job/cron feature to run that command
every 5 minutes, using the same production `DATABASE_URL` as the API. This
job must run against production only after the deployment's database and
secrets are configured. Do not point it at a developer database.

## Important operational rule

Passing the scheduled date alone does not prove the funeral happened. The
scheduled job can move a confirmed case to `in_progress`, but it does not
silently mark the funeral itself as completed. An authorised staff member must
record the arrangement as completed after the burial/cremation has happened;
the linked case then advances automatically to `completed`. This prevents
postponed funerals from being falsely reported as completed.
