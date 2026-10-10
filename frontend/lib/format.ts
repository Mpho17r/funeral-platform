/* ============================================================
   Shared display helpers.

   Money arrives from the API as decimal strings ("7000.00"), so it
   is converted with Number() only for display.
============================================================ */

type ApiErrorShape = {
  response?: {
    status?: number;
    data?: { detail?: unknown };
  };
};

export function statusOf(err: unknown): number | undefined {
  return (err as ApiErrorShape)?.response?.status;
}

export function getApiErrorMessage(
  err: unknown,
  fallback: string
): string {
  const detail = (err as ApiErrorShape)?.response?.data?.detail;

  // A bare permission failure reads better in plain words. A 403 that
  // explains a rule (such as needing the override permission) keeps
  // the server's own message.
  if (
    statusOf(err) === 403 &&
    (typeof detail !== "string" ||
      detail.startsWith("Permission required"))
  ) {
    return "You do not have permission to do that.";
  }

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item: unknown) => {
        if (typeof item === "string") {
          return item;
        }

        const entry = item as { msg?: string; loc?: unknown[] };

        if (entry?.msg) {
          const location = Array.isArray(entry.loc)
            ? entry.loc.filter((part) => part !== "body").join(".")
            : "";

          return location
            ? `${location}: ${entry.msg}`
            : entry.msg;
        }

        return "Invalid request.";
      })
      .join(" ");
  }

  return fallback;
}

export function formatMoney(value: string | number | null) {
  return Number(value || 0).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatPercent(value: string | number) {
  return `${Number(value).toLocaleString("en-ZA", {
    maximumFractionDigits: 2,
  })}%`;
}

export function formatDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString("en-ZA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function formatStatus(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
