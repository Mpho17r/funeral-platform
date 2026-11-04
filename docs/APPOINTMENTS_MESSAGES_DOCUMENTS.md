# Appointments, customer messages and documents

## Appointments (`/appointments`)
- Book a person in: title, start, length, optional staff member, saved customer or typed contact, place, notes.
- A staff member cannot be double-booked, and a booking on a day they are on approved leave is refused. Both can be overridden on purpose (`allow_clash`).
- Statuses: scheduled, confirmed, completed, no-show, cancelled (a reason is required to cancel).
- Appointments show on the calendar. "Only my schedule" narrows to your own.
- **Remind customers the day before** (switch on the page): a reminder is queued once per appointment time, only when there is a phone number or email.

## Messages (`/messages`)
- Everything sent to customers is kept here, with what is still waiting.
- **Email** goes out by itself when SMTP is set up on the server; otherwise it waits to be sent.
- **WhatsApp and SMS are never sent automatically.** The page opens WhatsApp or the phone's SMS app with the text filled in; press "I have sent it" afterwards.
- Overdue-invoice reminders can be queued from Receivables.

## Documents (`/documents`)
- Contracts, receipts, licences, policies and other files for the whole business, optionally linked to a customer, with an optional expiry date (an alert is raised before it runs out).
- Archive and restore instead of deleting.

## Permissions
`appointments.view/manage`, `outbox.view/manage`, `library.view/manage`. Managers and finance get messages and documents; most roles can see appointments. Run `python3 -m app.seed_permissions` after pulling.

## Update steps
See `docs/UPDATING.md` (this release adds one database migration).
