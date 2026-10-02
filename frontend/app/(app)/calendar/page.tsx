"use client";

import { useEffect, useMemo, useState } from "react";

import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Clock3,
  Loader2,
  RefreshCw,
  Scissors,
  Search,
} from "lucide-react";

import { useRouter } from "next/navigation";

import api from "@/lib/api";

import { isAuthenticated } from "@/lib/auth";

type CalendarEvent = {
  id: string;
  event_type: string;
  title: string;
  date: string;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  description: string | null;
  venue: string | null;
  assigned_to: string | null;
  assigned_to_name: string | null;
  status: string | null;
};

type CalendarDay = {
  date: Date;
  dateKey: string;
  isCurrentMonth: boolean;
};

function getApiErrorMessage(err: any, fallback: string) {
  const detail = err?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item: any) => {
        if (typeof item === "string") {
          return item;
        }

        if (item?.msg) {
          return item.msg;
        }

        return "Invalid request.";
      })
      .join(" ");
  }

  if (typeof err?.message === "string") {
    return err.message;
  }

  return fallback;
}

function formatDateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function parseEventDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);

  return new Date(year, month - 1, day);
}

function formatMonthYear(date: Date) {
  return date.toLocaleDateString("en-ZA", {
    month: "long",
    year: "numeric",
  });
}

function formatEventDate(value: string) {
  return parseEventDate(value).toLocaleDateString("en-ZA", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatEventType(value: string) {
  switch (value) {
    case "funeral":
      return "Funeral";
    case "service":
      return "Service";
    case "task":
      return "Task";
    default:
      return value
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }
}

function getEventTypeClass(value: string) {
  switch (value) {
    case "funeral":
      return "bg-purple-100 text-purple-700 border-purple-200";
    case "service":
      return "bg-blue-100 text-blue-700 border-blue-200";
    case "task":
      return "bg-amber-100 text-amber-700 border-amber-200";
    default:
      return "bg-slate-100 text-slate-700 border-slate-200";
  }
}

function getEventTypeDotClass(value: string) {
  switch (value) {
    case "funeral":
      return "bg-purple-500";
    case "service":
      return "bg-blue-500";
    case "task":
      return "bg-amber-500";
    default:
      return "bg-slate-400";
  }
}

function getEventIcon(value: string) {
  switch (value) {
    case "funeral":
      return CalendarDays;
    case "service":
      return Scissors;
    case "task":
      return ClipboardList;
    default:
      return Clock3;
  }
}

function buildCalendarDays(month: Date): CalendarDay[] {
  const year = month.getFullYear();
  const monthIndex = month.getMonth();

  const firstDay = new Date(year, monthIndex, 1);
  const firstWeekday = firstDay.getDay();

  const daysInMonth = new Date(
    year,
    monthIndex + 1,
    0
  ).getDate();

  const previousMonthDays = new Date(
    year,
    monthIndex,
    0
  ).getDate();

  const days: CalendarDay[] = [];

  for (let index = firstWeekday - 1; index >= 0; index -= 1) {
    const day = new Date(
      year,
      monthIndex - 1,
      previousMonthDays - index
    );

    days.push({
      date: day,
      dateKey: formatDateKey(day),
      isCurrentMonth: false,
    });
  }

  for (let dayNumber = 1; dayNumber <= daysInMonth; dayNumber += 1) {
    const day = new Date(year, monthIndex, dayNumber);

    days.push({
      date: day,
      dateKey: formatDateKey(day),
      isCurrentMonth: true,
    });
  }

  let nextDay = 1;

  while (days.length < 42) {
    const day = new Date(
      year,
      monthIndex + 1,
      nextDay
    );

    days.push({
      date: day,
      dateKey: formatDateKey(day),
      isCurrentMonth: false,
    });

    nextDay += 1;
  }

  return days;
}

export default function CalendarWorkspacePage() {
  const router = useRouter();

  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [currentMonth, setCurrentMonth] = useState(
    new Date()
  );
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    loadEvents();
  }, [router]);

  async function loadEvents() {
    try {
      setLoading(true);
      setPageError("");

      const response = await api.get<CalendarEvent[]>(
        "/calendar"
      );

      setEvents(response.data);
    } catch (err: any) {
      if (err.response?.status === 401) {
        router.push("/login");
        return;
      }

      setPageError(
        getApiErrorMessage(
          err,
          "Unable to load the calendar workspace."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  const eventTypes = useMemo(() => {
    return Array.from(
      new Set(events.map((event) => event.event_type))
    ).sort();
  }, [events]);

  const filteredEvents = useMemo(() => {
    const query = search.trim().toLowerCase();

    return events.filter((event) => {
      const matchesType =
        typeFilter === "all" ||
        event.event_type === typeFilter;

      if (!matchesType) {
        return false;
      }

      if (!query) {
        return true;
      }

      const searchableText = [
        event.title,
        event.case_number,
        event.deceased_full_name,
        event.description,
        event.venue,
        event.assigned_to_name,
        event.status,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return searchableText.includes(query);
    });
  }, [events, search, typeFilter]);

  const eventsByDate = useMemo(() => {
    const grouped = new Map<string, CalendarEvent[]>();

    filteredEvents.forEach((event) => {
      const existing = grouped.get(event.date) ?? [];

      existing.push(event);

      grouped.set(event.date, existing);
    });

    return grouped;
  }, [filteredEvents]);

  const calendarDays = useMemo(() => {
    return buildCalendarDays(currentMonth);
  }, [currentMonth]);

  const upcomingEvents = useMemo(() => {
    const todayKey = formatDateKey(new Date());

    return [...filteredEvents]
      .filter((event) => event.date >= todayKey)
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(0, 8);
  }, [filteredEvents]);

  const todayKey = formatDateKey(new Date());

  function goToPreviousMonth() {
    setCurrentMonth(
      (previous) =>
        new Date(
          previous.getFullYear(),
          previous.getMonth() - 1,
          1
        )
    );
  }

  function goToNextMonth() {
    setCurrentMonth(
      (previous) =>
        new Date(
          previous.getFullYear(),
          previous.getMonth() + 1,
          1
        )
    );
  }

  function goToToday() {
    setCurrentMonth(new Date());
  }

  function openCase(caseId: string) {
    router.push(`/cases/${caseId}`);
  }

  return (
    <main className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-slate-100 p-3">
              <CalendarDays className="h-6 w-6 text-slate-700" />
            </div>

            <div>
              <h1 className="text-2xl font-semibold text-slate-900">
                Calendar
              </h1>

              <p className="text-sm text-slate-500">
                Unified operational schedule
              </p>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={loadEvents}
          disabled={loading}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
          <div className="w-full lg:flex-1">
            <label
              htmlFor="calendar-search"
              className="mb-1 block text-sm font-medium text-slate-700"
            >
              Search
            </label>

            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />

              <input
                id="calendar-search"
                type="search"
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Event, case, deceased, venue or staff..."
                className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-slate-500"
              />
            </div>
          </div>

          <div className="w-full lg:w-52">
            <label
              htmlFor="calendar-type-filter"
              className="mb-1 block text-sm font-medium text-slate-700"
            >
              Event type
            </label>

            <select
              id="calendar-type-filter"
              value={typeFilter}
              onChange={(event) =>
                setTypeFilter(event.target.value)
              }
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500"
            >
              <option value="all">All events</option>

              {eventTypes.map((type) => (
                <option key={type} value={type}>
                  {formatEventType(type)}
                </option>
              ))}
            </select>
          </div>

          <div className="text-sm text-slate-500">
            Showing{" "}
            <span className="font-semibold text-slate-800">
              {filteredEvents.length}
            </span>{" "}
            events
          </div>
        </div>
      </section>

      {pageError && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {pageError}
        </div>
      )}

      {loading ? (
        <section className="flex items-center justify-center rounded-xl border border-slate-200 bg-white px-6 py-20 text-sm text-slate-500 shadow-sm">
          <div className="flex items-center gap-2">
            <Loader2 className="h-5 w-5 animate-spin" />
            Loading calendar...
          </div>
        </section>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-col gap-3 border-b border-slate-200 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={goToPreviousMonth}
                  className="rounded-lg border border-slate-200 p-2 text-slate-600 transition hover:bg-slate-50"
                  aria-label="Previous month"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>

                <button
                  type="button"
                  onClick={goToToday}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                >
                  Today
                </button>

                <button
                  type="button"
                  onClick={goToNextMonth}
                  className="rounded-lg border border-slate-200 p-2 text-slate-600 transition hover:bg-slate-50"
                  aria-label="Next month"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>

              <h2 className="text-lg font-semibold text-slate-900">
                {formatMonthYear(currentMonth)}
              </h2>
            </div>

            <div className="grid grid-cols-7 border-b border-slate-200 bg-slate-50">
              {[
                "Sun",
                "Mon",
                "Tue",
                "Wed",
                "Thu",
                "Fri",
                "Sat",
              ].map((day) => (
                <div
                  key={day}
                  className="border-r border-slate-200 px-2 py-2 text-center text-xs font-semibold uppercase tracking-wide text-slate-500 last:border-r-0"
                >
                  {day}
                </div>
              ))}
            </div>

            <div className="grid grid-cols-7">
              {calendarDays.map((day) => {
                const dayEvents =
                  eventsByDate.get(day.dateKey) ?? [];

                const isToday =
                  day.dateKey === todayKey;

                return (
                  <div
                    key={day.dateKey}
                    className={`min-h-28 border-b border-r border-slate-200 p-2 last:border-r-0 ${
                      day.isCurrentMonth
                        ? "bg-white"
                        : "bg-slate-50"
                    }`}
                  >
                    <div className="mb-2 flex justify-end">
                      <span
                        className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium ${
                          isToday
                            ? "bg-slate-900 text-white"
                            : day.isCurrentMonth
                              ? "text-slate-700"
                              : "text-slate-400"
                        }`}
                      >
                        {day.date.getDate()}
                      </span>
                    </div>

                    <div className="space-y-1">
                      {dayEvents
                        .slice(0, 3)
                        .map((event) => (
                          <button
                            key={event.id}
                            type="button"
                            onClick={() =>
                              openCase(event.case_id)
                            }
                            className={`group flex w-full items-start gap-1.5 rounded-md border px-2 py-1 text-left text-xs transition hover:shadow-sm ${getEventTypeClass(
                              event.event_type
                            )}`}
                            title={`${event.title} — ${event.case_number}`}
                          >
                            <span
                              className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${getEventTypeDotClass(
                                event.event_type
                              )}`}
                            />

                            <span className="min-w-0 truncate font-medium">
                              {event.title}
                            </span>
                          </button>
                        ))}

                      {dayEvents.length > 3 && (
                        <div className="px-2 text-xs font-medium text-slate-500">
                          +{dayEvents.length - 3} more
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex flex-wrap gap-4 border-t border-slate-200 px-4 py-3">
              {["funeral", "service", "task"].map(
                (type) => (
                  <div
                    key={type}
                    className="flex items-center gap-2 text-xs text-slate-600"
                  >
                    <span
                      className={`h-2.5 w-2.5 rounded-full ${getEventTypeDotClass(
                        type
                      )}`}
                    />

                    {formatEventType(type)}
                  </div>
                )
              )}
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-5 py-4">
              <div className="flex items-center gap-2">
                <Clock3 className="h-5 w-5 text-slate-600" />

                <div>
                  <h2 className="font-semibold text-slate-900">
                    Upcoming events
                  </h2>

                  <p className="text-xs text-slate-500">
                    Next scheduled operational items
                  </p>
                </div>
              </div>
            </div>

            {upcomingEvents.length === 0 ? (
              <div className="px-5 py-12 text-center">
                <CalendarDays className="mx-auto mb-3 h-10 w-10 text-slate-300" />

                <h3 className="font-semibold text-slate-800">
                  No upcoming events
                </h3>

                <p className="mt-1 text-sm text-slate-500">
                  There are no scheduled events matching
                  the current filters.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {upcomingEvents.map((event) => {
                  const EventIcon = getEventIcon(
                    event.event_type
                  );

                  return (
                    <button
                      key={event.id}
                      type="button"
                      onClick={() =>
                        openCase(event.case_id)
                      }
                      className="flex w-full gap-3 px-5 py-4 text-left transition hover:bg-slate-50"
                    >
                      <div
                        className={`mt-0.5 rounded-lg border p-2 ${getEventTypeClass(
                          event.event_type
                        )}`}
                      >
                        <EventIcon className="h-4 w-4" />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${getEventTypeClass(
                              event.event_type
                            )}`}
                          >
                            {formatEventType(
                              event.event_type
                            )}
                          </span>

                          <span className="text-xs text-slate-500">
                            {formatEventDate(event.date)}
                          </span>
                        </div>

                        <div className="mt-1 truncate font-medium text-slate-900">
                          {event.title}
                        </div>

                        <div className="mt-1 text-xs text-slate-500">
                          {event.case_number} ·{" "}
                          {event.deceased_full_name}
                        </div>

                        {event.venue && (
                          <div className="mt-1 truncate text-xs text-slate-400">
                            {event.venue}
                          </div>
                        )}

                        {event.assigned_to_name && (
                          <div className="mt-1 text-xs text-slate-400">
                            Assigned to{" "}
                            {event.assigned_to_name}
                          </div>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
