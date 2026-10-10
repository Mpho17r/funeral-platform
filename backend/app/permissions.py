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
    "members.delete": "Delete members",

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

    # Staff presence
    "presence.view": "View staff presence",
    "presence.manage": "Manage staff presence",

    # Reports
    "reports.view": "View reports",

    # Settings
    "settings.view": "View business settings",
    "settings.manage": "Manage business settings",

    # Branding
    "branding.view": "View business branding",
    "branding.manage": "Manage business branding",

    # Resources (vehicles, venues, equipment)
    "resources.view": "View vehicles, venues and equipment",
    "resources.manage": "Manage vehicles, venues and equipment",

    # Resource bookings
    "resource_bookings.view": "View resource bookings and availability",
    "resource_bookings.manage": "Create, change and cancel resource bookings",

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
