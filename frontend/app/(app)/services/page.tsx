"use client";

import { HeartHandshake, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ErrorNote } from "@/components/Notices";
import api from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { formatMoney, formatStatus, getApiErrorMessage } from "@/lib/format";

type ServiceRow = {
  id: string;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  service_type: string;
  service_name: string;
  status: string;
  quantity: number;
  total_price: string;
  scheduled_date: string | null;
  provider: string | null;
};

type Page = { total: number; items: ServiceRow[] };
type Options = { statuses: string[]; types: string[] };

const PAGE_SIZE = 50;

const field =
  "h-10 rounded-lg border border-[var(--fos-border)] bg-[var(--fos-surface)] px-3 text-sm text-[var(--fos-text)] focus:outline-none focus:ring-2 focus:ring-[var(--fos-focus)]";

export default function ServicesPage() {
  const router = useRouter();

  const [rows, setRows] = useState<ServiceRow[]>([]);
  const [total, setTotal] = useState(0);
  const [options, setOptions] = useState<Options>({ statuses: [], types: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  // Search waits for a pause in typing instead of asking on every key.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300);

    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    api
      .get<Options>("/services/options")
      .then((response) => setOptions(response.data))
      .catch(() => undefined);
  }, []);

  const load = useCallback(
    async (offset: number) => {
      try {
        setLoading(true);
        setError("");

        const response = await api.get<Page>("/services", {
          params: {
            q: query || undefined,
            status: status || undefined,
            service_type: type || undefined,
            date_from: from || undefined,
            date_to: to || undefined,
            limit: PAGE_SIZE,
            offset,
          },
        });

        setTotal(response.data.total);
        setRows((current) =>
          offset === 0
            ? response.data.items
            : [...current, ...response.data.items],
        );
      } catch (err) {
        setError(getApiErrorMessage(err, "Could not load services."));
      } finally {
        setLoading(false);
      }
    },
    [query, status, type, from, to],
  );

  useEffect(() => {
    void load(0);
  }, [load]);

  const filtered = Boolean(query || status || type || from || to);

  return (
    <div className="mx-auto max-w-6xl p-6 md:p-8">
      <h1 className="text-2xl font-bold">Services</h1>
      <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
        Every service booked across your cases, soonest first. Open a row to
        work on it inside its case.
      </p>

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="relative min-w-[14rem] flex-1">
          <span className="sr-only">Search services</span>
          <Search
            size={16}
            className="pointer-events-none absolute left-3 top-3 text-[var(--fos-text-muted)]"
          />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search service, provider, case or name"
            className={`${field} w-full pl-9`}
          />
        </label>

        <label>
          <span className="sr-only">Status</span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className={field}
          >
            <option value="">Any status</option>
            {options.statuses.map((value) => (
              <option key={value} value={value}>
                {formatStatus(value)}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span className="sr-only">Type</span>
          <select
            value={type}
            onChange={(event) => setType(event.target.value)}
            className={field}
          >
            <option value="">Any type</option>
            {options.types.map((value) => (
              <option key={value} value={value}>
                {formatStatus(value)}
              </option>
            ))}
          </select>
        </label>

        <label className="text-xs text-[var(--fos-text-muted)]">
          From
          <input
            type="date"
            value={from}
            onChange={(event) => setFrom(event.target.value)}
            className={`${field} mt-1 block`}
          />
        </label>

        <label className="text-xs text-[var(--fos-text-muted)]">
          To
          <input
            type="date"
            value={to}
            onChange={(event) => setTo(event.target.value)}
            className={`${field} mt-1 block`}
          />
        </label>

        {filtered && (
          <button
            type="button"
            onClick={() => {
              setSearch("");
              setStatus("");
              setType("");
              setFrom("");
              setTo("");
            }}
            className="h-10 rounded-lg px-3 text-sm font-medium text-[var(--fos-text-secondary)] underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {error && (
        <div className="mt-4">
          <ErrorNote message={error} />
        </div>
      )}

      <div className="mt-4 overflow-x-auto rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)]">
        <table className="w-full min-w-[44rem] text-left text-sm">
          <thead className="bg-[var(--fos-surface-muted)] text-xs uppercase text-[var(--fos-text-muted)]">
            <tr>
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3">Service</th>
              <th className="px-4 py-3">Case</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Total</th>
            </tr>
          </thead>

          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                tabIndex={0}
                onClick={() => router.push(`/cases/${row.case_id}/services`)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    router.push(`/cases/${row.case_id}/services`);
                  }
                }}
                className="cursor-pointer border-t border-[var(--fos-border)] transition hover:bg-[var(--fos-surface-muted)] focus:bg-[var(--fos-surface-muted)] focus:outline-none"
              >
                <td className="whitespace-nowrap px-4 py-3">
                  {row.scheduled_date ? (
                    formatDateTime(row.scheduled_date)
                  ) : (
                    <span className="text-[var(--fos-text-muted)]">
                      Not scheduled
                    </span>
                  )}
                </td>

                <td className="px-4 py-3">
                  <div className="font-medium">{row.service_name}</div>
                  <div className="text-xs text-[var(--fos-text-muted)]">
                    {formatStatus(row.service_type)}
                    {row.provider ? ` · ${row.provider}` : ""}
                  </div>
                </td>

                <td className="px-4 py-3">
                  <div className="font-medium">{row.case_number}</div>
                  <div className="text-xs text-[var(--fos-text-muted)]">
                    {row.deceased_full_name}
                  </div>
                </td>

                <td className="px-4 py-3">{formatStatus(row.status)}</td>

                <td className="whitespace-nowrap px-4 py-3 text-right">
                  {formatMoney(row.total_price)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {!loading && rows.length === 0 && (
          <div className="flex flex-col items-center px-6 py-14 text-center">
            <HeartHandshake
              size={28}
              className="text-[var(--fos-text-muted)]"
            />
            <p className="mt-3 font-medium">
              {filtered ? "No services match" : "No services yet"}
            </p>
            <p className="mt-1 max-w-sm text-sm text-[var(--fos-text-muted)]">
              {filtered
                ? "Try a different search or clear the filters."
                : "Services are added inside a case, under Services. They will all appear here."}
            </p>
            {!filtered && (
              <button
                type="button"
                onClick={() => router.push("/cases")}
                className="mt-4 rounded-xl bg-[var(--fos-primary)] px-4 py-2 text-sm font-semibold text-[var(--fos-on-primary)]"
              >
                Open cases
              </button>
            )}
          </div>
        )}

        {loading && rows.length === 0 && (
          <p className="px-6 py-10 text-center text-sm text-[var(--fos-text-muted)]">
            Loading…
          </p>
        )}
      </div>

      {rows.length > 0 && (
        <div className="mt-4 flex items-center justify-between text-sm text-[var(--fos-text-muted)]">
          <span>
            Showing {rows.length} of {total}
          </span>

          {rows.length < total && (
            <button
              type="button"
              disabled={loading}
              onClick={() => load(rows.length)}
              className="rounded-lg border border-[var(--fos-border)] px-4 py-2 font-medium text-[var(--fos-text)] transition hover:bg-[var(--fos-surface-muted)] disabled:opacity-50"
            >
              {loading ? "Loading…" : "Show more"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
