"use client";

import {
  Activity,
  CalendarDays,
  CreditCard,
  FileText,
  HeartHandshake,
  LayoutDashboard,
  LogOut,
  Settings,
  Users,
  UserRound,
  ClipboardList,
  FolderOpen,
  ShieldCheck,
  Receipt,
} from "lucide-react";

import { usePathname, useRouter } from "next/navigation";

import { removeToken } from "@/lib/auth";
import { useBranding } from "@/components/BrandingProvider";
import { useTheme } from "@/components/ThemeProvider";

type SidebarProps = {
  onLogout?: () => void;
};

export default function Sidebar({
  onLogout,
}: SidebarProps) {
  const router = useRouter();
  const pathname = usePathname();

  const {
    branding,
    logoObjectUrl,
  } = useBranding();

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
      label: "Contributions",
      icon: <Receipt size={18} />,
      path: "/membership-contributions",
    },
    {
      label: "Payments",
      icon: <CreditCard size={18} />,
      path: "/membership-payments",
    },
  ];

  const records = [
    {
      label: "Contacts",
      icon: <UserRound size={18} />,
      path: "/contacts",
    },
    {
      label: "Documents",
      icon: <FolderOpen size={18} />,
      path: "/documents",
    },
    {
      label: "Tasks",
      icon: <ClipboardList size={18} />,
      path: "/tasks",
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
      label: "Settings",
      icon: <Settings size={18} />,
      path: "/settings",
    },
  ];

  function isActive(path: string) {
    if (path === "/dashboard") {
      return pathname === "/dashboard";
    }

    return (
      pathname === path ||
      pathname.startsWith(`${path}/`)
    );
  }

  function NavItem({
    label,
    icon,
    path,
  }: {
    label: string;
    icon: React.ReactNode;
    path: string;
  }) {
    const active = isActive(path);

    return (
      <button
        type="button"
        onClick={() => navigate(path)}
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
                backgroundColor:
                  branding?.primary_color ||
                  "#0f172a",
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
                  color:
                    branding?.secondary_color ||
                    "currentColor",
                }
          }
        >
          {icon}
        </span>

        <span className="truncate">
          {label}
        </span>
      </button>
    );
  }

  function SectionTitle({
    children,
  }: {
    children: React.ReactNode;
  }) {
    return (
      <p
        className={`
          px-3 pb-2 pt-5 text-[10px]
          font-semibold uppercase tracking-[0.14em]
          ${
            resolvedTheme === "dark"
              ? "text-slate-500"
              : "text-slate-400"
          }
        `}
      >
        {children}
      </p>
    );
  }

  const businessName =
    branding?.name || "FuneralOS";

  const primary =
    branding?.primary_color || "#0f172a";

  const secondary =
    branding?.secondary_color || "#64748b";

  return (
    <aside
      className="
        flex h-screen w-64 shrink-0 flex-col
        border-r
        transition-colors duration-200
      "
      style={{
        backgroundColor:
          resolvedTheme === "dark"
            ? "#0f172a"
            : "#ffffff",

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
                {businessName
                  .charAt(0)
                  .toUpperCase()}
              </span>
            )}
          </div>

          <div className="min-w-0 text-left">
            <h1
              className={`
                truncate font-bold
                ${
                  resolvedTheme === "dark"
                    ? "text-white"
                    : "text-slate-950"
                }
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
        />

        <SectionTitle>
          Operations
        </SectionTitle>

        {operations.map((item) => (
          <NavItem
            key={item.path}
            label={item.label}
            icon={item.icon}
            path={item.path}
          />
        ))}

        <SectionTitle>
          Membership
        </SectionTitle>

        {membership.map((item) => (
          <NavItem
            key={item.path}
            label={item.label}
            icon={item.icon}
            path={item.path}
          />
        ))}

        <SectionTitle>
          Records
        </SectionTitle>

        {records.map((item) => (
          <NavItem
            key={item.path}
            label={item.label}
            icon={item.icon}
            path={item.path}
          />
        ))}

        <SectionTitle>
          Administration
        </SectionTitle>

        {administration.map((item) => (
          <NavItem
            key={item.path}
            label={item.label}
            icon={item.icon}
            path={item.path}
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