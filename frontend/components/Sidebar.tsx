"use client";

import {
  CalendarDays,
  CreditCard,
  FileText,
  LayoutDashboard,
  LayoutGrid,
  LogOut,
  ScrollText,
  Settings,
  Users,
  UserRound,
  ClipboardList,
  ShieldCheck,
  Receipt,
  UsersRound,
  UserCheck,
  ClipboardCheck,
  Truck,
  CalendarClock,
  Building,
  Boxes,
  BadgeCheck,
  Scale,
  Store,
  Wallet,
  Snowflake,
  MessageSquare,
  Activity,
  CircleHelp,
  Sparkles,
  FileUp,
  HeartHandshake,
  Tags,
  Car,
} from "lucide-react";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

import api from "@/lib/api";
import { ROUTE_PERMISSIONS } from "@/lib/access";
import { useCurrentUser } from "@/components/CurrentUserProvider";

import { removeToken } from "@/lib/auth";
import { useBranding } from "@/components/BrandingProvider";
import { useTheme } from "@/components/ThemeProvider";

type SidebarProps = {
  onLogout?: () => void;
  onNavigate?: () => void;
};

function isSidebarPathActive(pathname: string, path: string) {
  if (path === "/dashboard") {
    return pathname === "/dashboard";
  }

  return pathname === path || pathname.startsWith(`${path}/`);
}

function NavItem({
  label,
  icon,
  path,
  onNavigate,
  badge = 0,
}: {
  label: string;
  icon: React.ReactNode;
  path: string;
  onNavigate?: () => void;
  badge?: number;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { branding } = useBranding();
  const { resolvedTheme } = useTheme();

  const active = isSidebarPathActive(pathname, path);

  return (
    <button
      type="button"
      onClick={() => {
        router.push(path);
        onNavigate?.();
      }}
      className={`
        group flex w-full items-center gap-3 rounded-xl
        px-3 py-3 text-sm font-medium
        transition-all duration-150
        ${
          active
            ? "text-white shadow-sm"
            : resolvedTheme === "dark"
              ? "text-slate-300 hover:bg-white/10 hover:text-white"
              : "text-slate-600 hover:bg-black/5 hover:text-slate-950"
        }
      `}
      style={
        active
          ? {
              backgroundColor: branding?.primary_color || "#0f172a",
            }
          : undefined
      }
    >
      <span
        className="shrink-0"
        style={
          active
            ? {
                color: "#ffffff",
              }
            : {
                color: branding?.secondary_color || "currentColor",
              }
        }
      >
        {icon}
      </span>
      <span className="truncate">{label}</span>
      {badge > 0 && (
        <span
          aria-label={`${badge} unread`}
          className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[11px] font-bold text-white"
        >
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </button>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  const { resolvedTheme } = useTheme();

  return (
    <p
      className={`
        px-3 pb-2 pt-5 text-[10px]
        font-semibold uppercase tracking-[0.14em]
        ${resolvedTheme === "dark" ? "text-slate-500" : "text-slate-400"}
      `}
    >
      {children}
    </p>
  );
}

function useChatUnread(): number {
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let stopped = false;

    function load() {
      if (document.hidden) return;

      api
        .get<{ unread: number }>("/chat/unread-count")
        .then((response) => {
          if (!stopped) setUnread(response.data.unread);
        })
        .catch(() => {});
    }

    load();
    const timer = window.setInterval(load, 10000);

    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, []);

  return unread;
}

export default function Sidebar({ onLogout, onNavigate }: SidebarProps) {
  const router = useRouter();
  const chatUnread = useChatUnread();
  const { can } = useCurrentUser();

  // Only the screens this person is allowed to open.
  function shown<T extends { path: string }>(items: T[]): T[] {
    return items.filter((item) => {
      const needed = ROUTE_PERMISSIONS[item.path];

      return !needed || can(needed);
    });
  }

  const { branding, logoObjectUrl } = useBranding();

  const { resolvedTheme } = useTheme();

  function navigate(path: string) {
    router.push(path);
  }

  function handleLogout() {
    removeToken();

    if (onLogout) {
      onLogout();
    }

    router.push("/login");
  }

  const operations = [
    {
      label: "Cases",
      icon: <FileText size={18} />,
      path: "/cases",
    },
    {
      label: "Families",
      icon: <Users size={18} />,
      path: "/families",
    },
    {
      label: "Members",
      icon: <UserRound size={18} />,
      path: "/members",
    },
    {
      label: "Services",
      icon: <HeartHandshake size={18} />,
      path: "/services",
    },
    {
      label: "Price list",
      icon: <Tags size={18} />,
      path: "/catalogue",
    },
    {
      label: "Partner drivers",
      icon: <Car size={18} />,
      path: "/transport",
    },
    {
      label: "Run sheet",
      icon: <ClipboardList size={18} />,
      path: "/run-sheet",
    },
    {
      label: "Mortuary",
      icon: <Snowflake size={18} />,
      path: "/mortuary",
    },
    {
      label: "Resources",
      icon: <Truck size={18} />,
      path: "/resources",
    },
    {
      label: "Schedule",
      icon: <CalendarClock size={18} />,
      path: "/resource-bookings",
    },
    {
      label: "Inventory",
      icon: <Boxes size={18} />,
      path: "/inventory",
    },
    {
      label: "Suppliers",
      icon: <Store size={18} />,
      path: "/suppliers",
    },
    {
      label: "Licences",
      icon: <BadgeCheck size={18} />,
      path: "/compliance",
    },
  ];

  const membership = [
    {
      label: "Membership Plans",
      icon: <ShieldCheck size={18} />,
      path: "/membership-plans",
    },
    {
      label: "Memberships",
      icon: <Users size={18} />,
      path: "/memberships",
    },
    {
      label: "Covered Dependents",
      icon: <Users size={18} />,
      path: "/covered-dependents",
    },
    {
      label: "Beneficiaries",
      icon: <UserCheck size={18} />,
      path: "/beneficiaries",
    },
    {
      label: "Claims",
      icon: <ClipboardCheck size={18} />,
      path: "/claims",
    },
    {
      label: "Contributions",
      icon: <Receipt size={18} />,
      path: "/membership-contributions",
    },
    {
      label: "Payments",
      icon: <CreditCard size={18} />,
      path: "/membership-payments",
    },
    {
      label: "Expenses",
      icon: <Wallet size={18} />,
      path: "/expenses",
    },
    {
      label: "Reconciliation",
      icon: <Scale size={18} />,
      path: "/reconciliation",
    },
    {
      label: "Reminders",
      icon: <MessageSquare size={18} />,
      path: "/communications",
    },
  ];

  const records = [
    {
      label: "Contacts",
      icon: <UserRound size={18} />,
      path: "/contacts",
    },
    {
      label: "Tasks",
      icon: <ClipboardList size={18} />,
      path: "/tasks",
    },
  ];

  const workspace = [
    {
      label: "My workstation",
      icon: <LayoutGrid size={18} />,
      path: "/workstation",
    },
    {
      label: "Groups",
      icon: <UsersRound size={18} />,
      path: "/groups",
    },
    {
      label: "Staff Workspace",
      icon: <Users size={18} />,
      path: "/staff",
    },
    {
      label: "Branches",
      icon: <Building size={18} />,
      path: "/branches",
    },
  ];

  const administration = [
    {
      label: "Calendar",
      icon: <CalendarDays size={18} />,
      path: "/calendar",
    },
    {
      label: "Reports",
      icon: <Activity size={18} />,
      path: "/reports",
    },
    {
      label: "Import data",
      icon: <FileUp size={18} />,
      path: "/import",
    },
    {
      label: "Audit trail",
      icon: <ScrollText size={18} />,
      path: "/audit",
    },
    {
      label: "Settings",
      icon: <Settings size={18} />,
      path: "/settings",
    },
    {
      label: "KAI",
      icon: <Sparkles size={18} />,
      path: "/assistant",
    },
    {
      label: "Guide",
      icon: <CircleHelp size={18} />,
      path: "/help",
    },
  ];

  const businessName = branding?.name || "FuneralOS";

  const primary = branding?.primary_color || "#0f172a";

  const secondary = branding?.secondary_color || "#64748b";

  return (
    <aside
      className="
        flex h-screen w-64 shrink-0 flex-col
        border-r
        transition-colors duration-200
      "
      style={{
        backgroundColor: resolvedTheme === "dark" ? "#0f172a" : "#ffffff",

        borderColor:
          resolvedTheme === "dark"
            ? "rgba(255,255,255,0.08)"
            : "rgba(15,23,42,0.08)",
      }}
    >
      {/* BRAND HEADER */}
      <div
        className="flex h-20 items-center border-b px-5"
        style={{
          borderColor:
            resolvedTheme === "dark"
              ? "rgba(255,255,255,0.08)"
              : "rgba(15,23,42,0.08)",
        }}
      >
        <button
          type="button"
          onClick={() => navigate("/dashboard")}
          className="flex min-w-0 items-center gap-3"
        >
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-xl shadow-sm"
            style={{
              backgroundColor: primary,
            }}
          >
            {logoObjectUrl ? (
              <img
                src={logoObjectUrl}
                alt={`${businessName} logo`}
                className="h-full w-full object-contain bg-white p-1"
              />
            ) : (
              <span className="text-lg font-bold text-white">
                {businessName.charAt(0).toUpperCase()}
              </span>
            )}
          </div>

          <div className="min-w-0 text-left">
            <h1
              className={`
                truncate font-bold
                ${resolvedTheme === "dark" ? "text-white" : "text-slate-950"}
              `}
            >
              {businessName}
            </h1>

            <p
              className="truncate text-xs"
              style={{
                color: secondary,
              }}
            >
              Funeral Management
            </p>
          </div>
        </button>
      </div>

      {/* NAVIGATION */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <NavItem
          label="Dashboard"
          icon={<LayoutDashboard size={18} />}
          path="/dashboard"
          onNavigate={onNavigate}
        />

        {shown(operations).length > 0 && (
          <SectionTitle>Operations</SectionTitle>
        )}

        {shown(operations).map((item) => (
          <NavItem
            key={item.path}
            label={item.label}
            icon={item.icon}
            path={item.path}
            onNavigate={onNavigate}
          />
        ))}

        {shown(membership).length > 0 && (
          <SectionTitle>Membership</SectionTitle>
        )}

        {shown(membership).map((item) => (
          <NavItem
            key={item.path}
            label={item.label}
            icon={item.icon}
            path={item.path}
            onNavigate={onNavigate}
          />
        ))}

        {shown(records).length > 0 && (
          <SectionTitle>Records</SectionTitle>
        )}

        {shown(records).map((item) => (
          <NavItem
            key={item.path}
            label={item.label}
            icon={item.icon}
            path={item.path}
            onNavigate={onNavigate}
          />
        ))}

        {shown(workspace).length > 0 && (
          <SectionTitle>Workspace</SectionTitle>
        )}

        {shown(workspace).map((item) => (
          <NavItem
            key={item.path}
            label={item.label}
            icon={item.icon}
            path={item.path}
            onNavigate={onNavigate}
            badge={item.path === "/staff" ? chatUnread : 0}
          />
        ))}

        {shown(administration).length > 0 && (
          <SectionTitle>Administration</SectionTitle>
        )}

        {shown(administration).map((item) => (
          <NavItem
            key={item.path}
            label={item.label}
            icon={item.icon}
            path={item.path}
            onNavigate={onNavigate}
          />
        ))}
      </nav>

      {/* BRAND ACCENT */}
      <div className="px-4 pb-3">
        <div
          className="h-1 rounded-full"
          style={{
            background: `linear-gradient(
              90deg,
              ${primary},
              ${secondary}
            )`,
          }}
        />
      </div>

      {/* LOGOUT */}
      <div
        className="border-t p-4"
        style={{
          borderColor:
            resolvedTheme === "dark"
              ? "rgba(255,255,255,0.08)"
              : "rgba(15,23,42,0.08)",
        }}
      >
        <button
          type="button"
          onClick={handleLogout}
          className={`
            flex w-full items-center gap-3 rounded-xl
            px-3 py-3 text-sm font-medium transition
            ${
              resolvedTheme === "dark"
                ? "text-slate-300 hover:bg-white/10 hover:text-white"
                : "text-slate-600 hover:bg-black/5 hover:text-slate-950"
            }
          `}
        >
          <LogOut size={18} />
          Logout
        </button>
      </div>
    </aside>
  );
}
