# Leave and timesheets

**Leave** (`/leave`)
- Anyone asks for leave: annual, sick, family, study, unpaid or other. Weekends are not counted.
- Annual leave comes from a yearly allowance (default 15 working days, set by a manager on the
  Team tab). Pending and approved requests both use the balance; rejected or cancelled ones give it back.
- Only sick leave can be asked for after the fact. Overlapping requests are refused.
- Main admin and managers are notified, approve or reject (a reason is required to reject), and the
  worker is notified of the decision. Nobody decides their own leave (except the main admin, who has
  no one above them).
- Approved leave shows on the calendar (everyone's for managers, your own for others), and KAI
  never gives work to someone who is on approved leave.
- Public holidays are not excluded yet.

**Timesheets** (`/timesheets`)
- Hours worked per day, from clock-in/out minus breaks, in the business time zone. A shift that
  runs past midnight is split between the days. Leave days are marked.
- Managers (`timesheets.manage`) see everyone's week and download it as CSV for payroll.

Permissions: `leave.request`, `timesheets.view` (everyone); `leave.manage`, `timesheets.manage` (managers).
