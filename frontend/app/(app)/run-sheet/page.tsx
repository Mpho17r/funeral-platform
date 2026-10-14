"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Phone,
  Truck,
} from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import {
  KIND_LABELS,
  formatDay,
  shiftDay,
  timeInSouthAfrica,
  todayInSouthAfrica,
  dateTimeInSouthAfrica,
  type RunSheet,
  type RunSheetItem,
} from "@/lib/arrangements";
import { useBranches } from "@/lib/branches";
import { ALL_BRANCHES, BranchFilter } from "@/components/BranchControls";
import { Banner } from "@/components/Notices";

const KIND_STYLE: Record<RunSheetItem["kind"], string> = {
  collection: "bg-amber-100 text-amber-800",
  wake: "bg-purple-100 text-purple-700",
  service: "bg-blue-100 text-blue-700",
  departure: "bg-indigo-100 text-indigo-700",
  committal: "bg-emerald-100 text-emerald-700",
  booking: "bg-slate-200 text-slate-700",
};

export default function RunSheetPage() {
  const router = useRouter();
  const { branches, multiple } = useBranches();

  const [day, setDay] = useState(todayInSouthAfrica());
  const [branch, setBranch] = useState(ALL_BRANCHES);
  const [sheet, setSheet] = useState<RunSheet | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setError("");

      const response = await api.get<RunSheet>("/run-sheet", {
        params: {
          date: day,
          ...(branch !== ALL_BRANCHES ? { branch_id: branch } : {}),
        },
      });

      setSheet(response.data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load the run sheet."));
    } finally {
      setLoading(false);
    }
  }, [day, branch]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  function goTo(next: string) {
    if (next) {
      setLoading(true);
      setDay(next);
    }
  }

  const isToday = day === todayInSouthAfrica();

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Run sheet</h1>
          <p className="text-sm text-slate-500">
            Every collection and funeral for the day, with what still
            needs doing.
          </p>
        </div>

        {multiple && (
          <BranchFilter
            branches={branches}
            value={branch}
            onChange={(value) => {
              setLoading(true);
              setBranch(value);
            }}
          />
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          aria-label="Previous day"
          onClick={() => goTo(shiftDay(day, -1))}
          className="rounded-lg border border-slate-300 bg-white p-2.5 text-slate-700 hover:bg-slate-50"
        >
          <ChevronLeft size={16} />
        </button>

        <input
          type="date"
          aria-label="Day"
          value={day}
          onChange={(event) => goTo(event.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-slate-900"
        />

        <button
          type="button"
          aria-label="Next day"
          onClick={() => goTo(shiftDay(day, 1))}
          className="rounded-lg border border-slate-300 bg-white p-2.5 text-slate-700 hover:bg-slate-50"
        >
          <ChevronRight size={16} />
        </button>

        {!isToday && (
          <button
            type="button"
            onClick={() => goTo(todayInSouthAfrica())}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Today
          </button>
        )}

        <p className="ml-1 text-sm font-semibold text-slate-900">
          {formatDay(day)}
        </p>
      </div>

      {error && (
        <Banner tone="error" onDismiss={() => setError("")}>
          {error}
        </Banner>
      )}

      {loading && !sheet && (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </p>
      )}

      {sheet && (
        <>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Collections" value={sheet.summary.collections} />
            <Stat label="Funerals" value={sheet.summary.funerals} />
            <Stat
              label="Need attention"
              value={sheet.summary.flagged_items}
              alert={sheet.summary.flagged_items > 0}
            />
            <Stat
              label="Overdue collections"
              value={sheet.summary.overdue_collections}
              alert={sheet.summary.overdue_collections > 0}
            />
          </dl>

          {sheet.overdue_collections.length > 0 && (
            <section
              aria-label="Overdue collections"
              className="space-y-3 rounded-xl border border-red-200 bg-red-50 p-4"
            >
              <h2 className="flex items-center gap-2 text-sm font-semibold text-red-800">
                <AlertTriangle size={16} />
                Collections that were due and are still open
              </h2>

              {sheet.overdue_collections.map((item) => (
                <Row
                  key={item.id}
                  item={item}
                  showDate
                  onOpen={() =>
                    router.push(`/cases/${item.case_id}/arrangement`)
                  }
                />
              ))}
            </section>
          )}

          {sheet.items.length === 0 ? (
            <p className="rounded-xl border p-6 text-sm text-slate-500">
              Nothing is scheduled for this day.
            </p>
          ) : (
            <ol className="space-y-3">
              {sheet.items.map((item) => (
                <li key={item.id}>
                  <Row
                    item={item}
                    onOpen={() =>
                      router.push(`/cases/${item.case_id}/arrangement`)
                    }
                  />
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  alert = false,
}: {
  label: string;
  value: number;
  alert?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        alert ? "border-red-200 bg-red-50" : ""
      }`}
    >
      <dt className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd
        className={`mt-1 text-2xl font-bold ${
          alert ? "text-red-700" : "text-slate-900"
        }`}
      >
        {value}
      </dd>
    </div>
  );
}

function Row({
  item,
  onOpen,
  showDate = false,
}: {
  item: RunSheetItem;
  onOpen: () => void;
  showDate?: boolean;
}) {
  const danger = item.flags.some((flag) => flag.severity === "danger");

  return (
    <div
      className={`rounded-xl border bg-white p-4 ${
        danger
          ? "border-red-300"
          : item.flags.length > 0
            ? "border-amber-300"
            : ""
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <p className="w-24 shrink-0 text-lg font-bold text-slate-900">
            {showDate
              ? dateTimeInSouthAfrica(item.at)
              : timeInSouthAfrica(item.at)}
            {item.ends_at && (
              <span className="block text-xs font-normal text-slate-500">
                until {timeInSouthAfrica(item.ends_at)}
              </span>
            )}
          </p>

          <div>
            <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-900">
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${KIND_STYLE[item.kind]}`}
              >
                {KIND_LABELS[item.kind]}
              </span>
              {item.title}
            </p>

            <button
              type="button"
              onClick={onOpen}
              className="mt-1 text-left text-sm text-slate-700 underline-offset-2 hover:underline"
            >
              {item.deceased_full_name} · {item.case_number}
            </button>

            {(item.location || item.address) && (
              <p className="mt-1 text-sm text-slate-600">
                {[item.location, item.address].filter(Boolean).join(" · ")}
              </p>
            )}

            {(item.vehicle || item.driver) && (
              <p className="mt-1 flex items-center gap-1.5 text-sm text-slate-600">
                <Truck size={14} />
                {[item.vehicle, item.driver].filter(Boolean).join(" · ")}
              </p>
            )}

            {item.contact_name || item.contact_phone ? (
              <p className="mt-1 flex items-center gap-1.5 text-sm text-slate-600">
                <Phone size={14} />
                {[item.contact_name, item.contact_phone]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            ) : null}
          </div>
        </div>

        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium capitalize text-slate-600">
          {item.status.replace("_", " ")}
        </span>
      </div>

      {item.flags.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {item.flags.map((flag) => (
            <li
              key={flag.code}
              className={`flex items-start gap-2 rounded-lg px-3 py-2 text-sm ${
                flag.severity === "danger"
                  ? "bg-red-50 text-red-700"
                  : "bg-amber-50 text-amber-800"
              }`}
            >
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              {flag.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
