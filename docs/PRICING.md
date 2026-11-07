# Pricing and plans

Each kind of business (funeral, other business) has its own plans. A plan has a monthly price **before VAT**, a number of included staff accounts and branches, and a flat price for each extra staff account or branch. VAT (15%) is added automatically and shown on every price. Nothing is ever blocked: past what a plan includes, the bill grows.

## Starting plans (all prices before VAT)

| Business | Plan | Price | Staff | Branches | Extra staff | Extra branch |
| --- | --- | --- | --- | --- | --- | --- |
| Funeral | Beginner | R800 | 5 | 1 | R60 | R60 (placeholder) |
| Funeral | Standard | R1 000 | 7 | 2 | R60 | R60 (placeholder) |
| Funeral | Enterprise | R1 800 (placeholder) | 15 | 5 | R60 | R60 |
| Other | Startup | R450 | 3 | 1 | R50 (placeholder) | R50 (placeholder) |
| Other | Standard | R950 | 6 | 2 | R50 (placeholder) | R50 (placeholder) |
| Other | Enterprise | R1 500 (placeholder) | 12 | 5 | R50 | R50 |

The Beginner/Startup/Standard prices, staff counts and funeral extra-staff price are the agreed ones. Branch counts for the other-business plans, extra-branch prices, the other-business extra-staff price and the Enterprise plans are starting guesses. Change any of them (and VAT, and the note under the prices) at `/platform`.

## Where it shows

- Right after registering, the business picks a plan (`/choose-plan`) with sliders for team size and branches. "Decide later" keeps the first plan.
- Public `/pricing` has the same picker for both kinds of business.
- Settings → Plan & billing (owner only, permission `subscription.view`): plan, usage, this month's bill with VAT, and a Change plan button.
- Adding a staff account or branch beyond the plan shows what it adds, including VAT.
- `/platform`: edit plans, VAT, give a business a special plan price, and download a monthly statements CSV.

## How the bill works

- The count used is the busiest day of the month (snapshot every six hours by the scheduler).
- No proration. Only **active** businesses are charged; trial, suspended and cancelled show R0.
- A special price replaces the plan price; extras follow the plan rates.

## Not included

No payment collection yet. Statements are produced for you to invoice from.

## Updating

Run `python3 -m alembic upgrade head`, then `python3 -m app.seed_permissions`, and restart the backend and scheduler.
