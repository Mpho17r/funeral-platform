# Business mode — FuneralOS for any business

A business is either **funeral** (the whole platform, unchanged) or **general** (any other business that wants to manage people, tasks and money). It is chosen on the **Create your account** page (`/register`) and stored as `business_type`.

## What a general business sees
- **Hidden, and refused by the server for everyone including the main admin:** cases, mortuary, remains, death records, memberships, families, claims, transport, portals, quotes/invoices on cases, and the other funeral screens. (It works by removing the funeral permissions, so nothing is merely painted over.)
- **Dashboard:** money received and spent this month, profit or loss, open work, team.
- **Tasks:** *New task* works without a case. Tick **Let KAI choose** and KAI first works out what kind of job it is (finance, sales, operations, admin, HR, tech, management), matches that to each person's **job title** and role, then prefers the least busy person who is at work today. Or pick people yourself; several can share one task.
- **Money** (`/money`): record money received, cancel mistakes (never deleted), see profit or loss this month and month by month. Money out goes in **Expenses** (categories suited to a business).
- **KAI chat:** "Create a task to chase the supplier invoices" — KAI proposes who and why; it acts only after you confirm. **KAI Autopilot** works for general businesses too (it does not invent funeral work).
- Setup checklist, guided tour and Guide page are the business versions.

## Funeral businesses
Nothing changes. Money and Tasks-without-a-case are not shown to them.

## Notes
- Public sign-up is open while developing. On a live system it closes after the first business unless `ALLOW_REGISTRATION=true` is set, which a multi-customer service needs.
- Behind the scenes a general business's tasks sit on one quiet container case numbered `WORK`; it is never shown as a case.
- Migration `c1a3b4c5d670`.
