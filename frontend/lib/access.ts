/** The permission each screen needs, matching what the API enforces. */
export const ROUTE_PERMISSIONS: Record<string, string> = {
  "/cases": "cases.view",
  "/families": "families.view",
  "/members": "members.view",
  "/services": "services.view",
  "/run-sheet": "run_sheet.view",
  "/mortuary": "mortuary.view",
  "/resources": "resources.view",
  "/resource-bookings": "resource_bookings.view",
  "/inventory": "inventory.view",
  "/suppliers": "suppliers.view",
  "/expenses": "expenses.view",
  "/reconciliation": "reconciliation.view",
  "/membership-plans": "membership_plans.view",
  "/memberships": "memberships.view",
  "/covered-dependents": "memberships.view",
  "/beneficiaries": "beneficiaries.view",
  "/claims": "claims.view",
  "/membership-contributions": "contributions.view",
  "/membership-payments": "payments.view",
  "/communications": "communications.view",
  "/contacts": "contacts.view",
  "/tasks": "tasks.view",
  "/groups": "groups.view",
  "/staff": "chat.use",
  "/branches": "branches.view",
  "/calendar": "cases.view",
  "/reports": "reports.view",
  "/import": "imports.run",
  "/audit": "audit.view",
  "/settings": "settings.view",
  "/settings/data": "data.export",
};

export type WorkArea = "general" | "mortuary" | "finance" | "operations";

export function permissionForPath(pathname: string): string | null {
  const match = Object.keys(ROUTE_PERMISSIONS)
    .filter((path) => pathname === path || pathname.startsWith(`${path}/`))
    .sort((a, b) => b.length - a.length)[0];

  return match ? ROUTE_PERMISSIONS[match] : null;
}

export const AREA_LABELS: Record<string, string> = {
  general: "General staff",
  mortuary: "Mortuary",
  finance: "Finance and memberships",
  operations: "Funeral operations",
};
