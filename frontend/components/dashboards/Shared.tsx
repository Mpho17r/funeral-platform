"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";

import { AREA_LABELS } from "@/lib/access";
import { titleOf, useCurrentUser } from "@/components/CurrentUserProvider";

function greeting() {
  const hour = new Date().getHours();

  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";

  return "Good evening";
}

export function DashboardHeader({ subtitle }: { subtitle: string }) {
  const { user, access } = useCurrentUser();
  const first = (user?.full_name ?? "").split(" ")[0];

  return (
    <div>
      <p className="text-sm text-[var(--fos-text-muted)]">
        {[AREA_LABELS[access?.work_area ?? "general"], titleOf(user)]
          .filter((part, i, all) => part && all.indexOf(part) === i)
          .join(" · ")}
      </p>
      <h1 className="mt-1 text-2xl font-bold text-[var(--fos-text)]">
        {greeting()}
        {first ? `, ${first}` : ""}
      </h1>
      <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
        {subtitle}
      </p>
    </div>
  );
}

export function Tile({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "neutral" | "warn";
}) {
  return (
    <div
      className={`rounded-xl border p-5 shadow-sm ${
        tone === "warn"
          ? "border-amber-300 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10"
          : "border-[var(--fos-border)] bg-[var(--fos-surface)]"
      }`}
    >
      <p className="text-sm text-[var(--fos-text-muted)]">{label}</p>
      <p className="mt-2 text-3xl font-bold text-[var(--fos-text)]">
        {value}
      </p>
      {hint && (
        <p className="mt-1 text-xs text-[var(--fos-text-muted)]">{hint}</p>
      )}
    </div>
  );
}

export function Panel({
  title,
  href,
  linkLabel,
  children,
}: {
  title: string;
  href?: string;
  linkLabel?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-[var(--fos-border)] bg-[var(--fos-surface)] shadow-sm">
      <div className="flex items-center justify-between border-b border-[var(--fos-border)] px-5 py-4">
        <h2 className="text-sm font-semibold text-[var(--fos-text)]">
          {title}
        </h2>
        {href && (
          <Link
            href={href}
            className="inline-flex items-center gap-1 text-xs font-medium text-[var(--fos-primary)] hover:underline"
          >
            {linkLabel ?? "Open"} <ArrowRight size={13} />
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

export function EmptyRow({ children }: { children: React.ReactNode }) {
  return (
    <p className="px-5 py-8 text-center text-sm text-[var(--fos-text-muted)]">
      {children}
    </p>
  );
}

export function QuickActions({
  actions,
}: {
  actions: { label: string; href: string }[];
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {actions.map((a) => (
        <Link
          key={a.href}
          href={a.href}
          className="rounded-lg bg-[var(--fos-primary)] px-4 py-2 text-sm font-semibold text-[var(--fos-on-primary)] hover:opacity-90"
        >
          {a.label}
        </Link>
      ))}
    </div>
  );
}

/** Loads one request and keeps the result, error and loading state. */
export function useLoad<T>(
  load: () => Promise<T>,
): { data: T | null; error: string; loading: boolean } {
  const [state, setState] = useState<{
    data: T | null;
    error: string;
    loading: boolean;
  }>({ data: null, error: "", loading: true });

  useEffect(() => {
    let cancelled = false;

    load()
      .then((data) => {
        if (!cancelled) setState({ data, error: "", loading: false });
      })
      .catch(() => {
        if (!cancelled) {
          setState({
            data: null,
            error: "Could not load this just now.",
            loading: false,
          });
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return state;
}
