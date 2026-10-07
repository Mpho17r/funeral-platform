# FuneralOS — Master Product Blueprint

**Status:** LOCKED — 7 October 2026  
**Owner:** Saccharum Technologies  
**Repository:** Mpho17r/funeral-platform  
**Product:** FuneralOS

## 1. Product vision

FuneralOS is a South African-first operating system for running a modern funeral business.

It is not merely a CRM, membership system, accounting package, fleet tracker, or case-management application. It is one connected operating environment in which people, cases, membership, services, documents, tasks, resources, communications, financials and management intelligence work together.

**Core promise:** one business, one system, one source of truth, connected workflows.

## 2. Product principles

1. **Case-centred:** the funeral case is the operational spine.
2. **Workflow-first:** modules must work together instead of becoming isolated pages.
3. **Trust-first:** tenant isolation, permissions, auditability, financial integrity and data protection are foundational.
4. **Calm UX:** software used around bereavement should feel clear, respectful and professional.
5. **South African first:** local funeral workflows, payments, communication, compliance and business realities matter.
6. **Mobile-capable:** field operations must eventually work beyond the office.
7. **Integration-friendly:** integrate where another provider is better than rebuilding everything.
8. **AI with purpose:** future AI must understand real FuneralOS data and workflows; no gimmick chatbot.
9. **Slow is acceptable; weak architecture is not.**
10. **Every major feature must improve an actual business workflow.**

## 3. The core model

### Case as the spine

A case will eventually connect:

- deceased
- family
- contacts
- membership and coverage
- services
- staff
- vehicles and transport
- venues
- documents
- tasks
- inventory
- communications
- financials
- claims
- audit history

The goal is that a manager can open one case and understand its operational state without hunting across unrelated modules.

## 4. Product domains

### Business core
- businesses and tenancy
- branches
- users
- roles and permissions
- teams/groups
- branding
- settings
- notifications
- documents
- search
- audit/activity
- platform administration (future Saccharum layer, separate from business Main Admin)

### People and membership
- families
- members
- dependents
- contacts
- membership plans
- contributions
- payments
- benefits
- coverage
- waiting periods
- arrears
- lapse
- reinstatement
- beneficiaries
- claims

### Funeral operations
- cases
- first-call/intake
- removal
- mortuary
- preparation
- coffins/products
- services
- venues
- staff assignment
- vehicles
- drivers
- equipment
- scheduling
- tasks/checklists
- dispatch
- inventory
- suppliers

### Business management
- quotes
- invoices
- receipts
- balances
- expenses
- collections
- reconciliation
- reports
- staff attendance
- branch management
- performance
- communications
- compliance workflows

### Experience layer
- family portal
- member portal
- agent portal
- staff/mobile experience
- digital forms
- signatures
- document sharing
- WhatsApp/SMS/email integrations
- multilingual experiences
- future FuneralOS Assistant

## 5. Workflow architecture

The long-term experience should be:

Case → requirements → services → resources → tasks → documents → communications → financials → completion → audit/history.

The system should increasingly identify operational gaps such as:

- missing documents
- overdue tasks
- unassigned responsibilities
- staff conflicts
- vehicle conflicts
- unpaid balances
- membership coverage issues
- approaching deadlines
- incomplete case information

The dashboard should answer:

1. What is happening?
2. What needs attention?
3. What is at risk?
4. What is coming?
5. How is the business performing?

## 6. Membership and coverage architecture

Keep these as separate concepts:

**Membership status engine:** Is the membership covered?

**Coverage decision engine:** What benefits does this case receive?

Do not collapse these engines into one service.

Membership must eventually support configurable:

- grace periods
- arrears
- lapse rules
- reinstatement rules
- waiting periods
- benefits
- dependents
- refunds/overpayments
- claims

## 7. Financial integrity

Financial records should become increasingly ledger-oriented and auditable.

Future capabilities:

- quotes
- invoices
- receipts
- payment allocation
- balances
- refunds
- overpayments
- reconciliation
- recurring membership payments
- payment reminders
- financial reporting
- branch reporting

Financial history should not be casually overwritten or destroyed.

## 8. Operations and physical resources

Future operations should connect:

Case → service → staff → vehicle → driver → venue → equipment → tasks → completion.

The platform should detect resource conflicts instead of relying entirely on staff memory.

Future capabilities include:

- fleet management
- dispatch
- GPS integrations
- vehicle availability
- driver assignments
- mortuary tracking
- inventory
- supplier management
- equipment
- resource scheduling
- chain-of-custody support where appropriate

## 9. Communication

Communication should be contextual to a case, member or workflow.

Future channels:

- WhatsApp
- SMS
- email
- in-app notifications

Future workflow examples:

- service confirmations
- document requests
- payment reminders
- membership reminders
- claim updates
- appointment reminders
- family notifications

## 10. Portals and mobile

Future family portal:
- funeral information
- schedules
- documents
- approvals/signatures
- balances where appropriate
- communication

Future member portal:
- membership
- dependents
- contributions
- payments
- benefits
- documents
- permitted profile updates

Future staff/mobile experience:
- assignments
- tasks
- schedules
- field updates
- driver workflows
- poor-connectivity/offline capability where justified

## 11. Intelligence and AI

FuneralOS intelligence should first focus on deterministic operational signals:

- overdue work
- missing information
- conflicts
- arrears
- upcoming deadlines
- workload
- incomplete cases
- unusual activity

Future AI should answer operational questions from authorised FuneralOS data, for example:

- What is still outstanding on this funeral?
- Which funerals tomorrow have no vehicle?
- Which memberships are in arrears?
- Which cases have missing documents?
- What was collected this month?

AI must respect permissions, tenancy, auditability and sensitive-data boundaries.

## 12. Security, privacy and trust

Production architecture must continue to prioritise:

- strict tenant isolation
- permission enforcement
- explicit user overrides
- audit trails
- sensitive-data protection
- secure document storage
- backups and recovery
- data export
- controlled deletion
- account deactivation
- historical record preservation
- security/session controls
- monitoring

POPIA-conscious design is a product requirement, not merely marketing copy.

## 13. Multi-branch architecture

Future business structure:

Company → branches → staff/resources/cases/members/financials.

Business Main Admin controls the funeral business.

Saccharum Platform Admin is a separate future layer responsible for platform-wide:

- businesses
- subscriptions
- usage
- users
- members
- cases
- storage
- feature usage
- platform health

Never confuse the two roles.

## 14. Commercial strategy

FuneralOS will be sold as SaaS.

Primary initial customer:

**small and medium South African funeral parlours that rely on paper, spreadsheets, WhatsApp and disconnected systems.**

Sales approach:

1. direct outreach
2. personalised demonstration
3. workflow assessment
4. guided trial
5. data migration/onboarding
6. first live cases
7. subscription
8. training/support
9. referrals

The demonstration should show a complete funeral workflow rather than a tour of disconnected pages.

## 15. Pricing strategy

Pricing architecture is locked; exact amounts remain open for customer validation.

Preferred model:

- base subscription influenced primarily by branch count
- configurable user limits
- member limits
- active-case limits
- storage limits
- communication limits
- advanced feature tiers
- enterprise/custom integrations

Future tiers may be:

- Starter
- Growth
- Professional
- Enterprise

Do not race to be the cheapest platform. Sell reduced administration, fewer mistakes, visibility, control and operational efficiency.

## 16. Onboarding as a product

Future onboarding should include:

- business setup
- branding
- branch setup
- staff setup
- permissions
- workflow configuration
- existing-data import
- membership migration
- training

Migration from spreadsheets and legacy records can become a major sales advantage.

## 17. What FuneralOS will not become

FuneralOS will not intentionally become:

- a generic ERP
- a generic social network
- a website builder
- a bank
- an insurer
- an accounting product trying to replace every accounting platform
- a generic HR suite
- an AI chatbot without operational value

Use integrations where appropriate.

## 18. UX direction

The interface should be:

- calm
- professional
- modern
- clear
- responsive
- accessible
- contextual
- operational

Avoid designing every screen as repeated cards + tables + buttons.

Design tools such as Canva, Lovable and Figma may be used as creative partners, but generated design/code must fit the existing architecture, permissions and APIs.

## 19. Development discipline

We are deliberately working without a deadline.

For each major area:

1. inspect the existing architecture
2. understand the real workflow
3. research only when useful
4. design the smallest sound model
5. implement backend rules first
6. add permissions and auditability
7. test thoroughly
8. connect the frontend
9. review UX
10. improve based on actual usage
11. only then move forward

No random feature chasing.

No premature rewrites.

No replacing working architecture simply because a new design looks better.

## 20. Quality gate

A feature is not considered finished merely because it works.

Before calling it complete, ask:

- Is the architecture clean?
- Is tenant isolation correct?
- Are permissions correct?
- Is historical data safe?
- Is the workflow genuinely better?
- Is failure handling sensible?
- Is it auditable?
- Does it integrate with the rest of FuneralOS?
- Can the design evolve?
- Is it suitable for future scale?
- Can it eventually support mobile/integrations/automation where relevant?

## 21. Product differentiation

FuneralOS aims to differentiate through the combination of:

- South African funeral-business understanding
- case-centred architecture
- connected operations
- membership/coverage intelligence
- branch management
- physical resource coordination
- financial integrity
- contextual communication
- strong auditability
- future mobile/offline workflows
- operational intelligence
- useful AI
- calm, modern UX

The objective is not to copy the strongest competitor.

The objective is to build a more coherent operating system.

## 22. Locked strategic statement

**FuneralOS is a South African-first operating system for the entire lifecycle of a funeral business — from member and family management, through case creation and funeral operations, to financial closure, communication, reporting and long-term business management.**

The platform should make it difficult for important work to fall through the cracks while giving management a clear view of what is happening, what needs attention, what is at risk and what should happen next.

**Blueprint status: LOCKED. Build from here.**
