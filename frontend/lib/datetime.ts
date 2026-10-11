// The API requires every datetime to carry a timezone offset, while
// <input type="datetime-local"> yields a bare local time. These helpers
// convert between the two, always in the browser's own timezone.

function pad(value: number) {
  return String(value).padStart(2, "0");
}

// "2026-10-12T09:00" (local) -> "2026-10-12T07:00:00.000Z"
export function localInputToIso(value: string): string | null {
  if (!value) {
    return null;
  }

  const date = new Date(value);

  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

// ISO string from the API -> "2026-10-12T09:00" for a datetime-local input
export function isoToLocalInput(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-` +
    `${pad(date.getDate())}T${pad(date.getHours())}:` +
    `${pad(date.getMinutes())}`
  );
}

// A case's funeral_date ("2026-10-12") at a given local hour.
export function dateAtHour(day: string, hour: number): string {
  return `${day}T${pad(hour)}:00`;
}

export function formatTime(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleTimeString("en-ZA", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function formatDateTime(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("en-ZA", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

// Local calendar day key, e.g. "2026-10-12", used to group bookings.
export function dayKey(value: string): string {
  const date = new Date(value);

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate()
  )}`;
}

export function formatDayHeading(key: string): string {
  const [year, month, day] = key.split("-").map(Number);
  const date = new Date(year, month - 1, day);

  const today = new Date();
  const todayKey = dayKey(today.toISOString());
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  const label = date.toLocaleDateString("en-ZA", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  if (key === todayKey) {
    return `Today · ${label}`;
  }

  if (key === dayKey(tomorrow.toISOString())) {
    return `Tomorrow · ${label}`;
  }

  return label;
}
