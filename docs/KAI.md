# KAI — Knowledge · Assistance · Intelligence

KAI is the assistant inside FuneralOS (sidebar → **KAI**). It replaces "Ask FuneralOS".

## What it does
- **Greets you** by name, with your branch, and a short briefing of what needs attention (only from real records you may see).
- **Follows the conversation**: "the second one", "that case", "her balance".
- **Finds what is missing** on a case, checks **collection readiness**, balances, tasks, funerals soon, vehicle bookings.
- **Organisation view** (branch comparison, backlogs) only for people with `branches.all_access`.
- **Prepares actions** (for example adding a follow-up task). Nothing changes until you press **Yes, do it**; your permission is checked again at that moment.

## Safeguards
- Every answer is a fresh query inside your own request, so branch limits and permissions apply exactly as on the normal screens.
- Memory stores ids and wording per person, never facts; facts are looked up again each time. If your access is gone, KAI says so.
- Conversations are private per user and can be cleared.
- Not a language model: KAI answers from rules over your data. When it does not understand or may not show something, it says so rather than guessing.

## API
`GET /kai/hello`, `POST /kai/message`, `GET|DELETE /kai/history`, `POST /kai/actions/{id}/confirm|cancel`. Migration `b4f6a7c8d903`.
