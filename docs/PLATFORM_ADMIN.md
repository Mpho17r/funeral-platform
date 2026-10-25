# Platform administration and plans

The platform owner (Saccharum Technologies) manages subscriptions separately from any funeral business. A business's Main Admin can never reach this layer.

## Creating the operator
`python -m app.create_platform_admin` (run once on the server; asks for email and password). Sign in at `/platform`.

## What it controls
- Plan tier (starter, growth, professional, enterprise) and status (trial, active, suspended, cancelled). Choosing a tier applies its starting limits; any limit can then be changed or cleared (blank = unlimited).
- Limits: branches, staff accounts, members, active cases. They are enforced whenever a record is saved, from any screen or import, and count every branch even for branch-limited staff.
- A suspended or cancelled business cannot sign in. Restoring it brings everyone back; no data is touched.
- New sign-ups start on a 30-day trial. A trial that passes its end date is not locked automatically yet: move it to active or suspended by hand.
- The operator sees counts only, never a business's records. Every change is audited against that business.

A business can see its own plan and usage at `GET /subscription`.

# Ask FuneralOS
`/assistant` answers fixed operational questions (arrears, upcoming funerals, funerals with nothing booked, overdue tasks, outstanding paperwork, money collected and owed, who is in the mortuary) from live data. It matches by wording, not by AI, and each question needs the same permission as the normal screen; branch limits apply.
