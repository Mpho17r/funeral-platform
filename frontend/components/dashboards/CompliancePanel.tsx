"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import api from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { EmptyRow, Panel } from "@/components/dashboards/Shared";

export type ComplianceItem = {
  id: string;
  kind_label: string;
  title: string;
  reference: string | null;
  expires_on: string;
  days_left: number;
  state: "expired" | "urgent" | "soon" | "ok";
};

export const STATE_STYLE: Record<ComplianceItem["state"], string> = {
  expired: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  urgent: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  soon: "bg-yellow-100 text-yellow-800 dark:bg-yellow-500/15 dark:text-yellow-200",
  ok: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
};

export function stateText(item: ComplianceItem) {
  if (item.days_left < 0) return `Expired ${-item.days_left} days ago`;
  if (item.days_left === 0) return "Expires today";
  return `${item.days_left} days left`;
}

/** The licences and certificates closest to running out. */
export function CompliancePanel() {
  const { can } = useCurrentUser();
  const [items, setItems] = useState<ComplianceItem[] | null>(null);

  useEffect(() => {
    if (!can("compliance.view")) return;
    api
      .get<{ items: ComplianceItem[] }>("/compliance")
      .then((r) => setItems(r.data.items))
      .catch(() => setItems([]));
  }, [can]);

  if (!can("compliance.view")) return null;

  return (
    <Panel title="Licences and certificates" href="/compliance" linkLabel="Manage">
      {items === null ? (
        <EmptyRow>Loading…</EmptyRow>
      ) : items.length === 0 ? (
        <EmptyRow>
          Nothing recorded yet.{" "}
          <Link href="/compliance" className="text-[var(--fos-primary)] underline">
            Add your certificate of competence
          </Link>{" "}
          so you are reminded before it expires.
        </EmptyRow>
      ) : (
        <ul className="divide-y divide-[var(--fos-border)]">
          {items.slice(0, 5).map((i) => (
            <li key={i.id} className="flex items-center gap-3 px-5 py-3 text-sm">
              <span className="min-w-0 flex-1">
                <span className="block font-medium text-[var(--fos-text)]">
                  {i.title}
                </span>
                <span className="block text-xs text-[var(--fos-text-muted)]">
                  {i.kind_label} · {formatDate(i.expires_on)}
                </span>
              </span>
              <span
                className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${STATE_STYLE[i.state]}`}
              >
                {stateText(i)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
