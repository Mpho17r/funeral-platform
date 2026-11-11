"use client";

import { useRouter, usePathname } from "next/navigation";
import { LogOut } from "lucide-react";

import { useBranding } from "@/components/BrandingProvider";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { LindaMark } from "@/components/LindaLogo";
import { GlobalSearch } from "@/components/GlobalSearch";
import { NotificationBell } from "@/components/NotificationBell";
import { ProfileMenu } from "@/components/ProfileMenu";
import { holds, isMembershipPath, ROUTE_PERMISSIONS } from "@/lib/access";

export type NavGroup = {
  title: string;
  items: { label: string; icon: React.ReactNode; path: string; badge?: number }[];
};

function isActive(pathname: string, path: string) {
  if (path === "/dashboard") return pathname === "/dashboard";
  return pathname === path || pathname.startsWith(`${path}/`);
}

/**
 * Glass layout, desktop: a floating icon rail down the left. Every screen the
 * person may open is here (hover for its name), grouped with thin dividers.
 */
export function GlassRail({
  groups,
  onLogout,
}: {
  groups: NavGroup[];
  onLogout: () => void;
}) {
  const router = useRouter();
  const pathname = usePathname();

  return (
    <nav
      aria-label="Main"
      className="glass-panel m-4 flex h-[calc(100vh-2rem)] w-[68px] flex-col items-center rounded-[28px] py-3"
    >
      <div className="glass-scroll flex w-full flex-1 flex-col items-center gap-1 overflow-y-auto px-2">
        {groups.map((group, index) => (
          <div key={group.title} className="flex w-full flex-col items-center gap-1">
            {index > 0 && (
              <span aria-hidden="true" className="my-1.5 h-px w-7 bg-white/15" />
            )}
            {group.items.map((item) => {
              const active = isActive(pathname, item.path);

              return (
                <button
                  key={item.path}
                  type="button"
                  data-tour={item.path}
                  title={item.label}
                  aria-label={item.label}
                  aria-current={active ? "page" : undefined}
                  onClick={() => router.push(item.path)}
                  className={`relative flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl transition ${
                    active
                      ? "bg-[#bfe0b0] text-[#14201a]"
                      : "text-white/75 hover:bg-white/12 hover:text-white"
                  }`}
                >
                  {item.icon}
                  {(item.badge ?? 0) > 0 && (
                    <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                      {item.badge! > 99 ? "99+" : item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      <button
        type="button"
        title="Log out"
        aria-label="Log out"
        onClick={onLogout}
        className="mt-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl text-white/75 transition hover:bg-white/12 hover:text-white"
      >
        <LogOut size={18} />
      </button>
    </nav>
  );
}

const FUNERAL_TABS: [string, string][] = [
  ["/dashboard", "Overview"],
  ["/cases", "Cases"],
  ["/families", "Families"],
  ["/memberships", "Memberships"],
  ["/calendar", "Calendar"],
];

const GENERAL_TABS: [string, string][] = [
  ["/dashboard", "Overview"],
  ["/customers", "Customers"],
  ["/appointments", "Appointments"],
  ["/sales", "Invoices"],
  ["/tasks", "Tasks"],
];

/** Glass layout, desktop: business name, the main tabs, then search, bell, profile. */
export function GlassTopBar() {
  const router = useRouter();
  const pathname = usePathname();
  const { branding, logoObjectUrl } = useBranding();
  const { can, isGeneral, membershipEnabled } = useCurrentUser();

  const name = branding?.name?.trim() || "LINDA";
  const tabs = (isGeneral ? GENERAL_TABS : FUNERAL_TABS)
    .filter(([path]) => {
      if (!membershipEnabled && isMembershipPath(path)) return false;
      const needed = ROUTE_PERMISSIONS[path];
      return !needed || holds(needed, can);
    })
    .slice(0, 5);

  return (
    <div className="flex w-full items-center gap-4">
      <button
        type="button"
        onClick={() => router.push("/dashboard")}
        className="flex min-w-0 shrink-0 items-center gap-3"
        aria-label={`${name} overview`}
      >
        {logoObjectUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={logoObjectUrl}
            alt=""
            className="h-10 w-10 rounded-xl bg-white/90 object-contain p-0.5"
          />
        ) : (
          <LindaMark size={40} className="rounded-xl" />
        )}
        <span className="max-w-[200px] truncate text-[15px] font-semibold text-white">
          {name}
        </span>
      </button>

      <div role="tablist" className="mx-auto flex items-center gap-1">
        {tabs.map(([path, label]) => {
          const active = isActive(pathname, path);

          return (
            <button
              key={path}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => router.push(path)}
              className={`relative px-3.5 py-2 text-sm font-medium transition ${
                active ? "text-[#bfe0b0]" : "text-white/75 hover:text-white"
              }`}
            >
              {label}
              {active && (
                <span className="absolute inset-x-3.5 -bottom-0.5 h-0.5 rounded-full bg-[#bfe0b0]" />
              )}
            </button>
          );
        })}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <GlobalSearch compact />
        <NotificationBell />
        <ProfileMenu />
      </div>
    </div>
  );
}
