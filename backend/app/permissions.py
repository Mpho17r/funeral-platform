"""FuneralOS permission catalogue.

Roles remain:

    main_admin
    manager
    staff

Permissions describe what a user is allowed to do.
"""

PERMISSIONS = {

    # Dashboard
    "dashboard.view": "View the business dashboard",

    # Cases
    "cases.view": "View funeral cases",
    "cases.create": "Create funeral cases",
    "cases.edit": "Edit funeral cases",
    "cases.archive": "Archive funeral cases",
    "cases.restore": "Restore archived funeral cases",
    "cases.delete": "Permanently delete funeral cases",

    # Families
    "families.view": "View families",
    "families.manage": "Manage families",

    # Members
    "members.view": "View members",
    "members.create": "Create members",
    "members.edit": "Edit members",
    "members.restore": "Restore archived members",
    "members.export": (
        "Download everything held about a member (a data access request)"
    ),
    "members.anonymise": (
        "Permanently remove a former member's personal details"
    ),
    "members.delete": "Archive members (they can be restored)",

    # Importing existing records
    "imports.run": "Import members and policies from a spreadsheet",

    # Membership plans
    "membership_plans.view": "View membership plans",
    "membership_plans.manage": "Manage membership plans",

    # Memberships
    "memberships.view": "View memberships",
    "memberships.create": "Create memberships",
    "memberships.edit": "Edit memberships",
    "memberships.manage": "Manage memberships",

    # Contributions
    "contributions.view": "View membership contributions",
    "contributions.create": "Record membership contributions",
    "contributions.edit": "Edit membership contributions",

    # Payments
    "payments.view": "View payments",
    "payments.create": "Record payments",
    "payments.edit": "Edit payments",
    "payments.delete": "Delete payments",

    # Funeral services
    "services.view": "View funeral services",
    "services.manage": "Manage funeral services",

    # Contacts
    "contacts.view": "View case contacts",
    "contacts.manage": "Manage case contacts",

    # Documents
    "documents.view": "View documents",
    "documents.manage": "Manage documents",

    # Tasks
    "tasks.view": "View tasks",
    "tasks.manage": "Manage tasks",
    "autopilot.view": "See and approve what KAI Autopilot does",

    # Money in and out (general businesses)
    "income.view": "See money received and the profit and loss",
    "income.manage": "Record and void money received",

    # Case financials
    "financials.view": "View case financial records",
    "financials.manage": "Manage case financial records",

    # Application users
    "users.view": "View business user accounts",
    "users.create": "Create business user accounts",
    "users.edit": "Edit business user accounts",
    "users.delete": "Delete business user accounts",

    # Employees
    "employees.view": "View employees",
    "employees.manage": "Manage employees",

    # Staff chat
    "chat.use": "Message colleagues and join channels",
    "chat.manage": (
        "Remove other people's messages and members from channels"
    ),

    "meetings.use": "Schedule and join meetings and calls",

    # Staff presence
    "presence.view": "View staff presence",
    "presence.manage": "Manage staff presence",

    # Reports
    "reports.view": "View reports",
    "finance.overview": "View the business-wide finance overview (money collected and owed)",

    # Audit trail
    "audit.view": "View the audit trail of who changed what",

    # Settings
    "settings.view": "View business settings",
    "settings.manage": "Manage business settings",

    # Data export (main admin only by default)
    "data.export": "Download a complete export of the business's data",

    # Branding
    "branding.view": "View business branding",
    "branding.manage": "Manage business branding",

    # Resources (vehicles, venues, equipment)
    "resources.view": "View vehicles, venues and equipment",
    "resources.manage": "Manage vehicles, venues and equipment",

    # Resource bookings
    "resource_bookings.view": "View resource bookings and availability",
    "resource_bookings.manage": "Create, change and cancel resource bookings",

    # Branches
    "branches.view": "View branches",
    "branches.all_access": (
        "Work across all branches (otherwise limited to own branch)"
    ),
    "branches.manage": (
        "Create, edit, deactivate and choose the main branch"
    ),
    "branches.transfer": (
        "Move cases, members, resources, stock and staff between "
        "branches"
    ),

    # Death records and paperwork
    "death_records.view": (
        "View how and where a person died, including cause of death"
    ),
    "death_records.manage": (
        "Capture and edit the death record of a case"
    ),
    "paperwork.view": "View the death paperwork checklist of a case",
    "paperwork.manage": (
        "Tick off, add and update death paperwork on a case"
    ),

    # Mortuary and custody of remains
    "mortuary.view": (
        "View mortuary locations and who is where right now"
    ),
    "mortuary.manage": (
        "Create and edit mortuary locations such as fridges and "
        "cold rooms"
    ),
    "remains.view": (
        "View the custody record and movement log of remains"
    ),
    "remains.manage": (
        "Take remains into care, move them, record preparation, "
        "identification and temperature"
    ),
    "remains.release": "Release remains to a family or undertaker",
    "viewings.view": "See scheduled family viewings of remains",
    "viewings.manage": "Schedule and cancel family viewings of remains",
    "transport.view": "See partner drivers, their cars and car jobs",
    "transport.manage": (
        "Register partner drivers and cars, create car jobs, assign "
        "drivers and record their pay"
    ),
    "portal.manage": (
        "Create and revoke private family and member portal links"
    ),
    "compliance.view": (
        "View licences and certificates and when they expire"
    ),
    "compliance.manage": (
        "Record, update and archive licences and certificates"
    ),
    "remains.release_override": (
        "Release remains even though required paperwork is missing, "
        "with a written reason"
    ),

    # Funeral arrangements, collections and the daily run sheet
    "arrangements.view": (
        "View the wake, service and burial arrangements of a case"
    ),
    "arrangements.manage": (
        "Plan, confirm, complete and cancel funeral arrangements"
    ),
    "collections.view": "View body collection call-outs",
    "collections.manage": (
        "Schedule, dispatch, complete and cancel body collections"
    ),
    "run_sheet.view": (
        "View the daily run sheet of collections and funerals"
    ),

    # Communications
    "communications.view": (
        "View reminders and messages, and preview which reminders are due"
    ),
    "communications.send": (
        "Queue reminders, write messages, mark them sent or cancel them, "
        "and record a member's contact preferences"
    ),
    "communications.templates": "Change the wording of reminders",

    # Inventory and suppliers
    "inventory.view": "View stock items and stock movements",
    "inventory.manage": (
        "Create and edit stock items and correct stock levels"
    ),
    "inventory.stock": (
        "Record stock received, issued and returned"
    ),
    "suppliers.view": "View suppliers",
    "suppliers.manage": "Create, edit and deactivate suppliers",

    # Expenses and reconciliation
    "expenses.view": "View business expenses",
    "expenses.manage": "Record, edit and void business expenses",
    "reconciliation.view": "View daily money reconciliation",
    "reconciliation.manage": "Reconcile counted money against the books",

    # Quotes, invoices and receipts
    "financial_documents.view": "View quotes and invoices",
    "financial_documents.manage": (
        "Create and edit draft quotes and invoices, record quote "
        "decisions and convert quotes into invoices"
    ),
    "financial_documents.issue": (
        "Issue quotes and invoices, which makes them permanent"
    ),
    "financial_documents.void": "Void issued quotes and invoices",
    "receipts.view": "View payment receipts",
    "receipts.issue": "Issue receipts for recorded payments",

    # Beneficiaries
    "beneficiaries.view": "View membership beneficiaries",
    "beneficiaries.manage": "Manage membership beneficiaries",

    # Claims
    "claims.view": "View membership claims",
    "claims.create": "Submit, edit and cancel membership claims",
    "claims.review": "Review, approve and reject membership claims",
    "claims.pay": "Mark approved membership claims as paid",
    "claims.override": (
        "Approve claims despite failed coverage or above plan limits"
    ),

    # User groups
    "groups.view": "View user groups",
    "groups.create": "Create user groups",
    "groups.manage": "Manage group members and group administrators",
    "groups.delete": "Delete user groups",
}


def permission_keys() -> list[str]:
    """Return all registered permission keys."""
    return list(PERMISSIONS.keys())
