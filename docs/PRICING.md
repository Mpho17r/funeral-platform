# Pricing and plans

One standard monthly price covers the whole platform. A business that grows pays a flat extra amount for each additional staff account and each additional branch. Nothing is ever blocked: the bill grows instead.

## The numbers

Set by the platform owner at `/platform` ("Prices"). Starting values (placeholders, change them before you launch):

| Item | Starting value |
| --- | --- |
| Standard price | R299 / month |
| Staff accounts included | 5 |
| Branches included | 1 |
| Each extra staff account | +R25 |
| Each extra branch | +R25 |

A short note (for example "Prices exclude VAT") can be shown under the prices.

## How the bill works

- The count used is the busiest day of the month. A usage snapshot is taken every six hours by the scheduler (`usage` job).
- No proration. Removing staff lowers next month, not this one.
- Only businesses with status **active** are charged. Trial, suspended and cancelled show R0.
- A business can have a **special standard price** (platform page, per business). Extras still follow the normal rates.
- Legacy plan tiers (starter, growth, ...) remain as optional hard caps. The default `standard` tier has none.

## Where to see it

- Public: `/pricing` with a calculator.
- Business owner: Settings → Plan & billing (permission `subscription.view`, owner only).
- Adding a staff account or branch shows what it will add.
- Platform owner: `/platform` → Download CSV for any month.

## Not included

There is no payment collection yet. Statements are produced for you to invoice from.

## Updating

Run `python3 -m alembic upgrade head`, then `python3 -m app.seed_permissions`, and restart the backend and scheduler.
