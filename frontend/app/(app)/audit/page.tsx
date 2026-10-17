"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { inputClass } from "@/components/Dialog";
import { Banner } from "@/components/Notices";

type AuditItem = {
  id: string;
  created_at: string;
  user_id: string | null;
  user_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  notes: string | null;
  details: Record<string, unknown> | null;
};

type AuditList = {
  total: number;
  limit: number;
  offset: number;
  items: AuditItem[];
};

type Filters = {
  actions: string[];
  entity_types: string[];
};

const PAGE_SIZE = 50;

// "member.anonymised" -> "Member anonymised"
function humanise(value: string) {
  const text = value.replace(/[._]/g, " ").trim();

  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatWhen(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export default function AuditTrailPage() {
  const [filters, setFilters] = useState<Filters>({
    actions: [],
    entity_types: [],
  });

  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [offset, setOffset] = useState(0);

  const [data, setData] = useState<AuditList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Filters>("/audit-logs/filters")
      .then((response) => setFilters(response.data))
      .catch(() => {
        /* The list still works without the filter choices. */
      });
  }, []);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const response = await api.get<AuditList>("/audit-logs", {
        params: {
          action: action || undefined,
          entity_type: entityType || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          limit: PAGE_SIZE,
          offset,
        },
      });

      setData(response.data);
    } catch (err) {
      setError(
        getApiErrorMessage(err, "Could not load the audit trail."),
      );
    } finally {
      setLoading(false);
    }
  }, [action, entityType, dateFrom, dateTo, offset]);

  useEffect(() => {
    async function initialize() {
      await load();
    }

    void initialize();
  }, [load]);

  function changeFilter(update: () => void) {
    update();
    setOffset(0);
    setOpen(null);
  }

  const total = data?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <main className="min-h-screen bg-slate-100 p-6 md:p-8">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-2xl font-bold text-slate-900">
          Audit trail
        </h1>

        <p className="mt-1 text-sm text-slate-500">
          Who did what, and when. Entries cannot be edited or removed.
          Passwords, ID numbers and the wording of messages are never
          copied into it.
        </p>

        <div className="mt-6 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-4">
          <label className="block text-xs font-medium text-slate-600">
            What happened
            <select
              value={action}
              onChange={(event) =>
                changeFilter(() => setAction(event.target.value))
              }
              className={`${inputClass} mt-1`}
            >
              <option value="">Everything</option>
              {filters.actions.map((value) => (
                <option key={value} value={value}>
                  {humanise(value)}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-xs font-medium text-slate-600">
            Kind of record
            <select
              value={entityType}
              onChange={(event) =>
                changeFilter(() => setEntityType(event.target.value))
              }
              className={`${inputClass} mt-1`}
            >
              <option value="">All records</option>
              {filters.entity_types.map((value) => (
                <option key={value} value={value}>
                  {humanise(value)}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-xs font-medium text-slate-600">
            From
            <input
              type="date"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={(event) =>
                changeFilter(() => setDateFrom(event.target.value))
              }
              className={`${inputClass} mt-1`}
            />
          </label>

          <label className="block text-xs font-medium text-slate-600">
            To
            <input
              type="date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={(event) =>
                changeFilter(() => setDateTo(event.target.value))
              }
              className={`${inputClass} mt-1`}
            />
          </label>
        </div>

        {error && (
          <div className="mt-5">
            <Banner tone="error" onDismiss={() => setError("")}>
              {error}
            </Banner>
          </div>
        )}

        <div className="mt-5 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          {loading && !data ? (
            <p className="flex items-center gap-2 p-6 text-sm text-slate-500">
              <Loader2 size={16} className="animate-spin" /> Loading…
            </p>
          ) : data && data.items.length === 0 ? (
            <p className="p-10 text-center text-sm text-slate-500">
              Nothing matches these filters.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="w-8 px-3 py-3" />
                    <th className="px-4 py-3">When</th>
                    <th className="px-4 py-3">Who</th>
                    <th className="px-4 py-3">What happened</th>
                    <th className="px-4 py-3">Record</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {data?.items.map((item) => {
                    const expandable =
                      item.details !== null &&
                      Object.keys(item.details).length > 0;
                    const isOpen = open === item.id;

                    return (
                      <Fragment key={item.id}>
                        <tr
                          className={
                            expandable
                              ? "cursor-pointer hover:bg-slate-50"
                              : undefined
                          }
                          onClick={() =>
                            expandable &&
                            setOpen(isOpen ? null : item.id)
                          }
                        >
                          <td className="px-3 py-3 text-slate-400">
                            {expandable &&
                              (isOpen ? (
                                <ChevronDown size={15} />
                              ) : (
                                <ChevronRight size={15} />
                              ))}
                          </td>

                          <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                            {formatWhen(item.created_at)}
                          </td>

                          <td className="px-4 py-3 text-slate-800">
                            {item.user_name ?? (
                              <span className="text-slate-400">
                                System
                              </span>
                            )}
                          </td>

                          <td className="px-4 py-3">
                            <p className="font-medium text-slate-900">
                              {humanise(item.action)}
                            </p>
                            {item.notes && (
                              <p className="text-xs text-slate-500">
                                {item.notes}
                              </p>
                            )}
                          </td>

                          <td className="px-4 py-3 text-slate-600">
                            {humanise(item.entity_type)}
                          </td>
                        </tr>

                        {isOpen && item.details && (
                          <tr className="bg-slate-50">
                            <td />
                            <td colSpan={4} className="px-4 py-3">
                              <dl className="grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
                                {Object.entries(item.details).map(
                                  ([key, value]) => (
                                    <div
                                      key={key}
                                      className="flex gap-2"
                                    >
                                      <dt className="shrink-0 font-medium text-slate-500">
                                        {humanise(key)}:
                                      </dt>
                                      <dd className="min-w-0 break-words text-slate-800">
                                        {typeof value === "object" &&
                                        value !== null
                                          ? JSON.stringify(value)
                                          : String(value)}
                                      </dd>
                                    </div>
                                  ),
                                )}
                              </dl>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {data && data.total > 0 && (
          <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
            <p>
              {from}–{to} of {total}
            </p>

            <div className="flex gap-2">
              <button
                type="button"
                disabled={offset === 0 || loading}
                onClick={() =>
                  setOffset(Math.max(0, offset - PAGE_SIZE))
                }
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-medium disabled:opacity-50"
              >
                Newer
              </button>

              <button
                type="button"
                disabled={offset + PAGE_SIZE >= total || loading}
                onClick={() => setOffset(offset + PAGE_SIZE)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-medium disabled:opacity-50"
              >
                Older
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
