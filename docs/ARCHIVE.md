# Archive and voice notes

## Archive
- Finished **tasks** (status completed) and **closed/cancelled cases** are archived: by hand ("Archive this task/case") or automatically N days after they finish (default 14, set 0 for off). The scheduler job `archive` runs every 6 hours.
- Archived items leave dashboards, workstation, task and case lists. They live under **Archive** (sidebar): search, open, **Restore**.
- **Main admin only:** set how long archived items are kept (never, 1 month … 10 years) and delete an archived item by hand (typed confirmation). Every archive, restore and delete is in the audit log.
- Cases with quotes, invoices, payments or claims are never deleted (the database refuses); they stay archived.
- API: `GET /archive?kind=cases|tasks`, `POST /archive/tasks/{id}/archive|restore`, `DELETE /archive/{kind}/{id}`, `GET|PUT /archive/settings`. Cases use the existing `/cases/{id}/archive` and `/restore`.

## Voice notes
Microphone button in chat: record, **Send**, the other person plays it in the message. Up to 5 minutes. Stored like other chat files and visible only to the conversation.

## Services work like tasks
A service on a case can be given to one or more people (**Give to someone**), who update its status (Not started → In progress → Completed). Responsible people get an alert when they open the platform. Finished services are archived automatically (Archive → Services); they stay on the case's invoice either way.

## What the family owes follows the invoice
The case account (amount due, paid, balance) now follows the case's live invoice, so a line added only on the invoice raises the amount due. With no invoice it is built from the services as before.

## Late work
Every 30 minutes the platform tells the people responsible, once, about tasks and services whose due time has passed.
