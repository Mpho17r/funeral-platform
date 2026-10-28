/** Guided tours: click-through lessons that follow a funeral from the
 * first call to the completed case. One tour per kind of work; managers
 * and main admins get the whole system. */

export type TourStep = {
  id: string;
  title: string;
  body: string;
  /** Page to open for this step. */
  path?: string;
  /** A page inside the practice case, e.g. "arrangement". "" = the case. */
  caseSub?: string;
  /** Menu item to point at: the path of the sidebar entry. */
  nav?: string;
  /** The person clicks the highlighted menu item to continue. */
  click?: boolean;
};

export type Tour = {
  id: string;
  title: string;
  summary: string;
  steps: TourStep[];
};

const welcome = (who: string): TourStep => ({
  id: "welcome",
  path: "/dashboard",
  title: "Welcome to FuneralOS",
  body: `This short tour is for ${who}. Click Next to move on, Back to go back, or Skip at any time. You can restart it from the Guide page.`,
});

const dashboard: TourStep = {
  id: "dashboard",
  path: "/dashboard",
  nav: "/dashboard",
  title: "Your dashboard",
  body: "Everything that needs attention today: funerals coming up, money owed, tasks and alerts. It only shows what your role is allowed to see.",
};

const workstation: TourStep = {
  id: "workstation",
  path: "/workstation",
  nav: "/workstation",
  title: "My workstation",
  body: "Your own starting point: the work assigned to you and the shortcuts you use most.",
};

const casesNav: TourStep = {
  id: "cases-nav",
  path: "/dashboard",
  nav: "/cases",
  click: true,
  title: "Step 1 · Every funeral is a case",
  body: "A funeral starts here. Click Cases in the menu.",
};

const casesList: TourStep = {
  id: "cases-list",
  path: "/cases",
  title: "Opening a case",
  body: "Use New case when a family calls: the deceased's name and next of kin are enough to start. Search and filters find any case later. Cases move from Open to In progress to Completed by themselves as the work happens, and you can always set the status yourself.",
};

const caseHome: TourStep = {
  id: "case-home",
  caseSub: "",
  title: "The case page",
  body: "One page for the whole funeral: status, family, money, documents, tasks. Everything below hangs off this page. The status moves on automatically, and every change is recorded.",
};

const deathRecord: TourStep = {
  id: "death-record",
  caseSub: "death-record",
  title: "Step 2 · Death record",
  body: "Record the date and cause of death and the paperwork checklist. For members, the cause decides which waiting period applies to their cover.",
};

const contacts: TourStep = {
  id: "contacts",
  caseSub: "contacts",
  title: "Step 3 · The family",
  body: "Add next of kin and other contacts. Reminders, messages and the private family link go to these people.",
};

const remains: TourStep = {
  id: "remains",
  caseSub: "remains",
  title: "Step 4 · Receiving the deceased",
  body: "Record who brought the deceased in, what came with them (belongings) and where they are stored. This starts the mortuary record and moves the case on by itself.",
};

const arrangement: TourStep = {
  id: "arrangement",
  caseSub: "arrangement",
  title: "Step 5 · Arranging the funeral",
  body: "Capture what the family has chosen: date, venue, burial or cremation, and the programme. Confirming it moves the case to Confirmed.",
};

const services: TourStep = {
  id: "services",
  caseSub: "services",
  title: "Step 6 · Services and items",
  body: "Add the services the family wants from your saved price list. Prices fill in by themselves and you can change one for this family. Stock is taken off automatically when an item is used.",
};

const catalogue: TourStep = {
  id: "catalogue",
  path: "/catalogue",
  nav: "/catalogue",
  title: "The price list",
  body: "Your standard services and packages are saved here once. Whatever you add to a case flows onto its quote and invoice, so nothing is typed twice.",
};

const quoteInvoice: TourStep = {
  id: "documents-money",
  caseSub: "financial/documents",
  title: "Step 7 · Quote and invoice",
  body: "Create a quote from the services on the case, then turn it into an invoice. VAT is worked out automatically at the rate your main admin set. Issued documents are locked; only voiding with a reason changes them.",
};

const payments: TourStep = {
  id: "payments",
  caseSub: "financial",
  title: "Step 8 · Payments",
  body: "Record each payment here. The amount paid, balance and status update by themselves. Overpayments show as credit.",
};

const caseDocuments: TourStep = {
  id: "case-documents",
  caseSub: "documents",
  title: "Step 9 · Documents",
  body: "Keep permits, forms and signed papers with the case. Access follows your permissions.",
};

const caseTasks: TourStep = {
  id: "case-tasks",
  caseSub: "tasks",
  title: "Step 10 · Tasks",
  body: "Everything still to do for this funeral, with who is responsible and when it is due. KAI can add follow-up tasks for you.",
};

const mortuary: TourStep = {
  id: "mortuary",
  path: "/mortuary",
  nav: "/mortuary",
  title: "Mortuary",
  body: "Storage spaces, temperature logs, handovers and belongings. A case is only ready for collection when its records are complete.",
};

const transport: TourStep = {
  id: "transport",
  path: "/transport",
  nav: "/transport",
  title: "Step 11 · Partner drivers and cars",
  body: "Hire people with cars for the day. Record each car's colour, make, model and type, then assign cars to funerals. Drivers get the venue, time and dress code on their private link, and you track their pay.",
};

const runSheet: TourStep = {
  id: "run-sheet",
  path: "/run-sheet",
  nav: "/run-sheet",
  title: "Step 12 · The run sheet",
  body: "The day's order of collections, services and burials, with vehicles and people. Check it the evening before.",
};

const schedule: TourStep = {
  id: "schedule",
  path: "/resource-bookings",
  nav: "/resource-bookings",
  title: "Schedule",
  body: "Book hearses, halls and equipment. Double-bookings are caught for you.",
};

const inventory: TourStep = {
  id: "inventory",
  path: "/inventory",
  nav: "/inventory",
  title: "Inventory",
  body: "Stock is deducted when a service uses it. When an item runs low you are alerted and can order from the supplier in one click.",
};

const suppliers: TourStep = {
  id: "suppliers",
  path: "/suppliers",
  nav: "/suppliers",
  title: "Suppliers",
  body: "Who you buy from, with their contact details, so reordering is quick.",
};

const reminders: TourStep = {
  id: "reminders",
  path: "/communications",
  nav: "/communications",
  title: "Messages and reminders",
  body: "Payment reminders and messages go out by email automatically, and you can see what was sent and what failed.",
};

const portal: TourStep = {
  id: "portal",
  caseSub: "",
  title: "Step 13 · Keep the family informed",
  body: "From the case page, create a private link for the family. They see the arrangements, the programme and what is outstanding. No password to remember, and you can switch the link off any time.",
};

const completing: TourStep = {
  id: "completing",
  caseSub: "",
  title: "Step 14 · Completing the case",
  body: "After the funeral, the case moves to Completed on its own. Check that everything is paid and every task is done, then close it. A closed case is kept as a permanent record.",
};

const calendar: TourStep = {
  id: "calendar",
  path: "/calendar",
  nav: "/calendar",
  title: "Calendar",
  body: "Funerals, viewings and bookings on one calendar.",
};

const tasksPage: TourStep = {
  id: "tasks-page",
  path: "/tasks",
  nav: "/tasks",
  title: "Your tasks",
  body: "All your tasks across cases, by due date.",
};

const kai: TourStep = {
  id: "kai",
  path: "/assistant",
  nav: "/assistant",
  title: "Meet KAI",
  body: "KAI is your assistant. Ask it what needs attention, whether a case is ready for collection, or what is missing on a case. It only shows what you are allowed to see, and it asks before it changes anything.",
};

const members: TourStep[] = [
  {
    id: "members",
    path: "/members",
    nav: "/members",
    title: "Members",
    body: "Everyone who pays for cover. Group them by region or branch. Covered family members sit under the member who pays.",
  },
  {
    id: "covered",
    path: "/covered-dependents",
    nav: "/covered-dependents",
    title: "Covered people, by paying member",
    body: "Each household is one section, opened by the paying member. Open a household to see who is covered.",
  },
  {
    id: "plans",
    path: "/membership-plans",
    nav: "/membership-plans",
    title: "Membership plans",
    body: "Your plans, what each covers and how much it costs. Waiting periods are set here.",
  },
  {
    id: "memberships",
    path: "/memberships",
    nav: "/memberships",
    title: "Memberships",
    body: "Who holds which plan, whether they are up to date, in arrears or lapsed.",
  },
  {
    id: "contributions",
    path: "/membership-contributions",
    nav: "/membership-contributions",
    title: "Contributions and payments",
    body: "What each member should pay each month, and what has actually come in.",
  },
  {
    id: "claims",
    path: "/claims",
    nav: "/claims",
    title: "Claims",
    body: "When a covered person dies, the claim is checked against the plan, the date and the waiting period.",
  },
];

const finance: TourStep[] = [
  {
    id: "expenses",
    path: "/expenses",
    nav: "/expenses",
    title: "Expenses",
    body: "Record what the business spends, by category and case.",
  },
  {
    id: "reconciliation",
    path: "/reconciliation",
    nav: "/reconciliation",
    title: "Reconciliation",
    body: "Match what you recorded against what hit the bank, and see what is unresolved.",
  },
  {
    id: "reports",
    path: "/reports",
    nav: "/reports",
    title: "Reports",
    body: "Cases, money and membership reports you can export.",
  },
];

const admin: TourStep[] = [
  {
    id: "staff",
    path: "/staff",
    nav: "/staff",
    title: "Your team",
    body: "Add staff, choose each person's role and branch, and adjust what they can access.",
  },
  {
    id: "branches",
    path: "/branches",
    nav: "/branches",
    title: "Branches",
    body: "Each branch sees its own cases and people. A person with all-branch access sees everything.",
  },
  {
    id: "settings",
    path: "/settings",
    nav: "/settings",
    title: "Settings",
    body: "Branding, attendance rules, membership rules and your tax are set here.",
  },
  {
    id: "tax",
    path: "/settings/tax",
    title: "Tax (VAT)",
    body: "The main admin sets your country's VAT rate (South Africa is 15%). It is added to quotes and invoices automatically.",
  },
  {
    id: "audit",
    path: "/audit",
    nav: "/audit",
    title: "Audit trail",
    body: "Who did what and when. Important changes are always recorded.",
  },
  {
    id: "import",
    path: "/import",
    nav: "/import",
    title: "Import your data",
    body: "Bring in existing members and cases from a spreadsheet.",
  },
];

const done: TourStep = {
  id: "done",
  path: "/dashboard",
  title: "You're all set",
  body: "That is the whole journey from the first call to a completed case. You can take this tour again, or another role's tour, from the Guide page.",
};

export const TOURS: Tour[] = [
  {
    id: "owner",
    title: "The whole system",
    summary: "Every part of FuneralOS, from the first call to a completed case, plus members, money and administration.",
    steps: [
      welcome("managers and main administrators"),
      dashboard,
      workstation,
      casesNav,
      casesList,
      caseHome,
      deathRecord,
      contacts,
      remains,
      arrangement,
      catalogue,
      services,
      quoteInvoice,
      payments,
      caseDocuments,
      caseTasks,
      mortuary,
      transport,
      runSheet,
      schedule,
      inventory,
      suppliers,
      reminders,
      portal,
      completing,
      ...members,
      ...finance,
      ...admin,
      kai,
      done,
    ],
  },
  {
    id: "staff",
    title: "Front-line staff",
    summary: "Opening a case, the family, arrangements, services, tasks and the day's run sheet.",
    steps: [
      welcome("front-line staff"),
      dashboard,
      casesNav,
      casesList,
      caseHome,
      deathRecord,
      contacts,
      arrangement,
      services,
      caseDocuments,
      caseTasks,
      runSheet,
      calendar,
      tasksPage,
      portal,
      completing,
      kai,
      done,
    ],
  },
  {
    id: "mortuary",
    title: "Mortuary team",
    summary: "Receiving the deceased, storage, handovers, belongings and collection.",
    steps: [
      welcome("the mortuary team"),
      workstation,
      casesNav,
      casesList,
      caseHome,
      remains,
      mortuary,
      caseTasks,
      inventory,
      completing,
      kai,
      done,
    ],
  },
  {
    id: "finance",
    title: "Finance and memberships",
    summary: "Price list, quotes and invoices with VAT, payments, memberships, claims and reconciliation.",
    steps: [
      welcome("finance and membership staff"),
      dashboard,
      catalogue,
      casesNav,
      casesList,
      services,
      quoteInvoice,
      payments,
      ...members,
      ...finance,
      completing,
      kai,
      done,
    ],
  },
  {
    id: "operations",
    title: "Funeral operations",
    summary: "The run sheet, partner drivers and cars, bookings, stock and suppliers.",
    steps: [
      welcome("funeral operations"),
      dashboard,
      casesNav,
      casesList,
      arrangement,
      runSheet,
      transport,
      schedule,
      inventory,
      suppliers,
      reminders,
      calendar,
      completing,
      kai,
      done,
    ],
  },
];

/** The tour that suits a role. */
export function tourForRole(role: string | null | undefined): Tour {
  const id =
    role === "main_admin" || role === "manager"
      ? "owner"
      : role === "mortuary" || role === "finance" || role === "operations"
        ? role
        : "staff";
  return TOURS.find((t) => t.id === id)!;
}
