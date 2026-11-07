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

## South African market snapshot

Public competitor prices checked on **7 November 2026**. These are directional comparisons, not like-for-like product evaluations; included members, users, support, onboarding, integrations and payment features differ.

| Product | Public monthly prices found | Positioning note |
| --- | --- | --- |
| [DignityFlow](https://dignityflow.co.za/) | R589 / R889 / R1,889, plus once-off setup fees of R3,500 / R6,500 / R15,500 | Funeral parlour CRM; multi-branch and member capacity increases by tier |
| [Funeral Service System](https://funeralservicesystem.com/pricing) | R199 / R299 / R699 / R849 | Member-count-led plans with limited admin/staff logins and bundled messaging credits |
| [FuneralPlus](https://funeralplus.co.za/) | R800 Basic / R1,800 Pro; Enterprise custom | Funeral planning, cases, billing, integrations and multi-branch features at higher tiers |
| [Policy Point](https://policypoint.co.za/) | R299 / R599 / R1,199 | More focused funeral policy/member administration |
| [Proppela](https://www.proppela.co.za/) | Starts at R1,750; published examples R2,350 / R3,550 / R7,750 | Larger funeral-business operating platform with assisted implementation |
| [Vivid Business](https://slgroup.co.za/vivid-business.html) | R299 | General SME finance/operations core with add-on modules |
| [Zentify](https://zentify.co.za/) | R299 / R399 / R599 | General SME business management with tiered user/storage limits |

### What this means for LINDA

The recommended funeral prices (R899 / R1,299 / R2,499) sit above the lower-cost funeral software segment and around or above some established multi-module offers. The general-business prices (R499 / R1,099 / R1,999) also position LINDA above many entry-level SME tools.

That is a **premium-value position**, not a low-cost position. It is defensible only if LINDA consistently demonstrates broader day-to-day operational coverage, dependable support, secure data handling, useful onboarding and measurable time savings. Do not compete by claiming more features alone; demonstrate real workflows and outcomes.

Before public launch:
- Interview funeral parlours and general businesses at different sizes; test price sensitivity and which capabilities they would actually pay for.
- Compare total first-year cost, including setup, migration, messaging credits, payment fees and support—not just the monthly headline.
- Test Standard as the intended core plan and track trial-to-paid conversion, churn, support hours and gross margin.
- Keep onboarding, data migration, training and bespoke integrations separately scoped and priced.
- If prospects consistently reject the entry tier, revisit packaging and included capacity before simply discounting every plan.

Competitor prices can change and should be rechecked before a public campaign. This snapshot does not establish market share, product quality or willingness-to-pay.

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
- Separate subscription-tier safety caps can restrict users, branches, members or active cases. They are distinct from the billable staff/branch inclusions; their interaction with metered overages is under review and must be made consistent before public launch.
- Trial, suspended and cancelled businesses currently show no amount due.
- The trial expiry policy remains a separate product decision.

## Implementation and approval notes

The figures in the table replace the earlier rough repository defaults. A migration updates only plan rows that still match the exact old seeded values; manually customised plans are preserved. New databases receive the recommended baseline from the seed defaults.

These are recommended starting targets, not a claim that willingness-to-pay has been validated. Before announcing prices publicly, review them against customer interviews, support cost, competitor alternatives and actual conversion data.