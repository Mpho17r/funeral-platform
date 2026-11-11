"use client";

import {
  CalendarCheck,
  FolderOpen,
  Mail,
  FileBarChart,
  Contact,
  HandCoins,
  Landmark,
  ReceiptText,
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
  CalendarOff,
  Timer,
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
  Archive,
  Bot,
  PiggyBank,
} from "lucide-react";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

import api from "@/lib/api";
import { ROUTE_PERMISSIONS, holds, MEMBERSHIP_PATHS } from "@/lib/access";
import { useCurrentUser } from "@/components/CurrentUserProvider";

import { removeToken } from "@/lib/auth";
import { LindaMark } from "@/components/LindaLogo";
import { useBranding } from "@/components/BrandingProvider";
import { PLATFORM_SLOGAN, platformLabel } from "@/lib/platform";
import { GlassRail } from "@/components/GlassNav";
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
  const active = isSidebarPathActive(pathname, path);

  return (
    <button
      type="button"
      data-tour={path}
      onClick={() => {
        router.push(path);
        onNavigate?.();
      }}
      className={`
        group relative flex w-full items-center gap-3 rounded-xl
        px-3 py-2.5 text-sm font-medium
        transition-colors duration-150
        ${
          active
            ? "bg-white/10 text-white"
            : "text-slate-300 hover:bg-white/5 hover:text-white"
        }
      `}
    >
      {active && (
        <span
          aria-hidden="true"
          className="absolute -left-3 top-2 bottom-2 w-1 rounded-r-full"
          style={{ backgroundColor: "var(--linda-gold)" }}
        />
      )}
      <span
        className="shrink-0"
        style={{ color: active ? "var(--linda-gold)" : "currentColor" }}
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
  return (
    <p
      className="
        px-3 pb-2 pt-5 text-[10px]
        font-semibold uppercase tracking-[0.14em] text-slate-500
      "
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
  const { can, membershipEnabled, access, isGeneral } = useCurrentUser();
  const { branding, logoObjectUrl } = useBranding();
  const businessName = branding?.name?.trim() || "LINDA";
  const platformText = access
    ? platformLabel(isGeneral)
    : PLATFORM_SLOGAN;

  // Only the screens this person is allowed to open.
  function shown<T extends { path: string }>(items: T[]): T[] {
    return items.filter((item) => {
      // A business that does not run memberships never sees those screens.
      if (!membershipEnabled && MEMBERSHIP_PATHS.has(item.path)) {
        return false;
      }

      const needed = ROUTE_PERMISSIONS[item.path];

      return !needed || holds(needed, can);
    });
  }

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
    {
      label: "Money",
      icon: <PiggyBank size={18} />,
      path: "/money",
    },
    {
      label: "Reports",
      icon: <FileBarChart size={18} />,
      path: "/business-reports",
    },
    {
      label: "Recurring & budgets",
      icon: <CalendarClock size={18} />,
      path: "/planning",
    },
    {
      label: "Customers",
      icon: <Contact size={18} />,
      path: "/customers",
    },
    {
      label: "Appointments",
      icon: <CalendarCheck size={18} />,
      path: "/appointments",
    },
    {
      label: "Messages",
      icon: <Mail size={18} />,
      path: "/messages",
    },
    {
      label: "Quotes & invoices",
      icon: <ReceiptText size={18} />,
      path: "/sales",
    },
    {
      label: "Who owes you",
      icon: <HandCoins size={18} />,
      path: "/receivables",
    },
    {
      label: "Bills you owe",
      icon: <Landmark size={18} />,
      path: "/bills",
    },
    {
      label: "Documents",
      icon: <FolderOpen size={18} />,
      path: "/documents",
    },
    {
      label: "KAI Autopilot",
      icon: <Bot size={18} />,
      path: "/autopilot",
    },
    {
      label: "Archive",
      icon: <Archive size={18} />,
      path: "/archive",
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
      label: "Leave",
      icon: <CalendarOff size={18} />,
      path: "/leave",
    },
    {
      label: "Timesheets",
      icon: <Timer size={18} />,
      path: "/timesheets",
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

  const { glassActive } = useTheme();

  // Glass look, desktop: the floating icon rail replaces this sidebar. (The
  // phone drawer passes onNavigate and keeps the full labelled list.)
  if (glassActive && !onNavigate) {
    const groups = [
      { title: "Home", items: [{ label: "Dashboard", icon: <LayoutDashboard size={18} />, path: "/dashboard" }] },
      { title: "Operations", items: shown(operations) },
      { title: "Finance", items: shown(membership) },
      { title: "Records", items: shown(records) },
      {
        title: "Workspace",
        items: shown(workspace).map((item) =>
          item.path === "/staff" ? { ...item, badge: chatUnread } : item,
        ),
      },
      { title: "Administration", items: shown(administration) },
    ].filter((group) => group.items.length > 0);

    return <GlassRail groups={groups} onLogout={handleLogout} />;
  }

  const line = "rgba(255,255,255,0.08)";

  return (
    <aside
      className="
        flex h-screen w-64 shrink-0 flex-col
        border-r text-slate-300
      "
      style={{
        backgroundColor: "var(--linda-navy)",
        borderColor: line,
      }}
    >
      {/* BRAND HEADER */}
      <div
        className="flex h-20 items-center border-b px-5"
        style={{ borderColor: line }}
      >
        <button
          type="button"
          data-tour="/dashboard"
          onClick={() => navigate("/dashboard")}
          className="flex min-w-0 items-center gap-3"
          aria-label="LINDA dashboard"
        >
          {logoObjectUrl ? (
            // The business's own logo takes the place of the LINDA mark.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={logoObjectUrl}
              alt={`${businessName} logo`}
              className="h-[38px] w-[38px] shrink-0 rounded-[10px] bg-white object-contain p-0.5 ring-1 ring-white/15"
            />
          ) : (
            <LindaMark size={38} className="shrink-0 rounded-[10px] ring-1 ring-white/15" />
          )}

          <div className="min-w-0 text-left">
            <h1
              className="truncate text-[15px] font-semibold leading-tight text-white"
              title={businessName}
            >
              {businessName}
            </h1>

            <p
              className="mt-1 text-[8.5px] font-semibold uppercase leading-tight tracking-[0.06em]"
              style={{ color: "var(--linda-gold)" }}
              data-testid="workspace-badge"
            >
              {platformText}
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
          <SectionTitle>{isGeneral || !membershipEnabled ? "Finance" : "Membership"}</SectionTitle>
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
          className="h-px"
          style={{
            background:
              "linear-gradient(90deg, var(--linda-gold), transparent)",
            opacity: 0.6,
          }}
        />
      </div>

      {/* LOGOUT */}
      <div className="border-t p-4" style={{ borderColor: line }}>
        <button
          type="button"
          onClick={handleLogout}
          className="
            flex w-full items-center gap-3 rounded-xl
            px-3 py-2.5 text-sm font-medium text-slate-300
            transition hover:bg-white/5 hover:text-white
          "
        >
          <LogOut size={18} />
          Logout
        </button>
      </div>
    </aside>
  );
}
