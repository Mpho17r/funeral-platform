# Archive and voice notes

## Archive
- Finished **tasks** (status completed) and **closed/cancelled cases** are archived: by hand ("Archive this task/case") or automatically N days after they finish (default 14, set 0 for off). The scheduler job `archive` runs every 6 hours.
- Archived items leave dashboards, workstation, task and case lists. They live under **Archive** (sidebar): search, open, **Restore**.
- **Main admin only:** set how long archived items are kept (never, 1 month … 10 years) and delete an archived item by hand (typed confirmation). Every archive, restore and delete is in the audit log.
- Cases with quotes, invoices, payments or claims are never deleted (the database refuses); they stay archived.
- API: `GET /archive?kind=cases|tasks`, `POST /archive/tasks/{id}/archive|restore`, `DELETE /archive/{kind}/{id}`, `GET|PUT /archive/settings`. Cases use the existing `/cases/{id}/archive` and `/restore`.

## Voice notes
Microphone button in chat: record, **Send**, the other person plays it in the message. Up to 5 minutes. Stored like other chat files and visible only to the conversation.
