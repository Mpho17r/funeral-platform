# LINDA pricing strategy

**Status:** Recommended commercial baseline for launch planning; not validated willingness-to-pay.  
**Currency:** South African rand (ZAR).  
**Prices below exclude VAT. VAT is added at the configured rate when applicable.**

## Recommended monthly plans

| Business type | Plan | Monthly price excl. VAT | Included staff | Included branches | Extra staff / month | Extra branch / month |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Funeral | Beginner | R899 | 5 | 1 | R60 | R149 |
| Funeral | Standard | R1,299 | 7 | 2 | R60 | R149 |
| Funeral | Enterprise | R2,499 | 15 | 5 | R60 | R149 |
| General | Startup | R499 | 3 | 1 | R50 | R99 |
| General | Standard | R1,099 | 6 | 2 | R50 | R99 |
| General | Enterprise | R1,999 | 12 | 5 | R50 | R99 |

Standard is the intended core revenue plan. Startup is an accessible entry point. Enterprise reflects greater included capacity and the operational overhead of serving larger businesses.

The extra-branch amounts are a separate recommendation from the earlier base-price proposal: branches create more operational overhead than an additional staff login, so they should not be priced at the same low add-on rate. The R149 funeral / R99 general branch add-ons are proposed launch assumptions and should be tested with real customer conversations before being treated as validated market prices.

## Commercial positioning

- All plans include the core LINDA feature set. Capacity and service level, not arbitrary feature locks, distinguish the tiers.
- Keep the Standard plan attractive as the natural choice for an established business.
- Offer paid onboarding, data migration, training and custom integrations as separately scoped services rather than hiding those costs in every subscription.
- Review actual support time, hosting, payment fees, onboarding effort, churn and customer feedback after the first cohort.
- Do not discount Enterprise below a sustainable support and operating cost.
- Show the price before VAT and the VAT-inclusive amount clearly. Never imply that a quote is cash collected or a payment receipt.

## Billing model currently implemented

- Plans are monthly and stored as integer cents.
- The existing engine calculates the month using peak recorded staff and branch counts.
- It currently has no recurring payment collection or payment-provider reconciliation. Statements are calculations, not proof of payment.
- There is no part-month proration in the current engine.
- Trial, suspended and cancelled businesses currently show no amount due.
- The trial expiry policy remains a separate product decision.

## Implementation and approval notes

The figures in the table replace the earlier rough repository defaults. A migration updates only plan rows that still match the exact old seeded values; manually customised plans are preserved. New databases receive the recommended baseline from the seed defaults.

These are recommended starting targets, not a claim that willingness-to-pay has been validated. Before announcing prices publicly, review them against customer interviews, support cost, competitor alternatives and actual conversion data.