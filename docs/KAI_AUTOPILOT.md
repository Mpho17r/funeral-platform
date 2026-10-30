# KAI Autopilot — KAI as platform manager (only when allowed)

**Sidebar → KAI Autopilot** (managers and main admins). The **Main Admin** chooses the mode:

| Mode | What happens |
|---|---|
| Off | KAI does nothing on its own. |
| Suggest | KAI works out what should happen and waits; a person approves or dismisses each item. |
| Automatic | KAI does it, logs every step as KAI, and every step has an **Undo**. |

## What KAI can do (each switch can be turned off)
- Create the tasks a case still needs: death record, paperwork, vehicle and drivers, payment follow-up, closing a finished case.
- Give unassigned tasks and services to the best person.
- Tell managers when work is late; a morning briefing.

**Choosing who:** active people allowed to see that kind of work, below the open-work limit; lowest workload first; people checked in today, on the case's branch and in the right work area come first. Main admins are used only when nobody else qualifies.

## What KAI can never do
Delete anything, change money, message a family, change a case's status, or change anyone's access. Everything it creates is an ordinary task or assignment people can edit, and is in the audit log as KAI.

## Also in this release
- Family portal shows **how to pay** (set under Settings → Business) with the case number as reference while something is owed.
- **Stock orders** archive (Archive → Stock orders); old notifications are cleaned up automatically.
- Ask KAI: "what services are waiting for me?", workload, and autopilot status.

Permission `autopilot.view` (managers); only the Main Admin can change the mode. Migrations `a9e1f2a3b458`, `b0f2a3b4c569`.
