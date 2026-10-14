export type Arrangement = {
  id: string;
  case_id: string;
  status: "draft" | "confirmed" | "completed" | "cancelled";
  wake_at: string | null;
  wake_venue: string | null;
  wake_address: string | null;
  service_at: string | null;
  service_venue_type: string | null;
  service_venue: string | null;
  service_address: string | null;
  officiant: string | null;
  departure_at: string | null;
  departure_point: string | null;
  committal_at: string | null;
  committal_place: string | null;
  committal_section: string | null;
  grave_number: string | null;
  grave_confirmed: boolean;
  notes: string | null;
  confirmed_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
};

export type Collection = {
  id: string;
  case_id: string;
  status: "scheduled" | "en_route" | "collected" | "cancelled";
  scheduled_at: string;
  pickup_type: string;
  pickup_address: string | null;
  pickup_contact_name: string | null;
  pickup_contact_phone: string | null;
  vehicle_resource_id: string | null;
  driver_user_id: string | null;
  en_route_at: string | null;
  collected_at: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  notes: string | null;
};

export type RunSheetFlag = {
  code: string;
  severity: "warning" | "danger";
  message: string;
};

export type RunSheetItem = {
  id: string;
  kind:
    | "collection"
    | "wake"
    | "service"
    | "departure"
    | "committal"
    | "booking";
  at: string;
  ends_at: string | null;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  title: string;
  location: string | null;
  address: string | null;
  contact_name: string | null;
  contact_phone: string | null;
  vehicle: string | null;
  driver: string | null;
  status: string;
  flags: RunSheetFlag[];
};

export type RunSheet = {
  date: string;
  timezone: string;
  branch_id: string | null;
  summary: {
    collections: number;
    funerals: number;
    items: number;
    flagged_items: number;
    overdue_collections: number;
  };
  items: RunSheetItem[];
  overdue_collections: RunSheetItem[];
};

export type VehicleOption = { id: string; name: string };
export type DriverOption = { id: string; full_name: string };

export const VENUE_TYPES = [
  { value: "church", label: "Church" },
  { value: "home", label: "Home" },
  { value: "chapel", label: "Chapel" },
  { value: "hall", label: "Hall" },
  { value: "graveside", label: "Graveside" },
  { value: "other", label: "Other" },
];

export const PICKUP_TYPES = [
  { value: "home", label: "Home" },
  { value: "hospital", label: "Hospital or clinic" },
  { value: "scene", label: "Scene of death" },
  { value: "mortuary", label: "Another mortuary" },
  { value: "other", label: "Other" },
];

export const ARRANGEMENT_STATUS: Record<
  Arrangement["status"],
  { label: string; style: string }
> = {
  draft: { label: "Draft", style: "bg-slate-200 text-slate-700" },
  confirmed: { label: "Confirmed", style: "bg-blue-100 text-blue-700" },
  completed: {
    label: "Completed",
    style: "bg-emerald-100 text-emerald-700",
  },
  cancelled: { label: "Cancelled", style: "bg-red-100 text-red-700" },
};

export const COLLECTION_STATUS: Record<
  Collection["status"],
  { label: string; style: string }
> = {
  scheduled: { label: "Scheduled", style: "bg-slate-200 text-slate-700" },
  en_route: { label: "On the way", style: "bg-amber-100 text-amber-800" },
  collected: {
    label: "Collected",
    style: "bg-emerald-100 text-emerald-700",
  },
  cancelled: { label: "Cancelled", style: "bg-red-100 text-red-700" },
};

export const KIND_LABELS: Record<RunSheetItem["kind"], string> = {
  collection: "Collection",
  wake: "Wake",
  service: "Service",
  departure: "Cortege",
  committal: "Burial",
  booking: "Booking",
};

export function labelOf(
  options: { value: string; label: string }[],
  value: string | null
): string {
  return options.find((o) => o.value === value)?.label ?? "—";
}

// Today as YYYY-MM-DD in South Africa, which is where a run sheet
// day is defined, whatever the browser's own timezone is.
export function todayInSouthAfrica(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Africa/Johannesburg",
  }).format(new Date());
}

export function shiftDay(day: string, delta: number): string {
  const [year, month, date] = day.split("-").map(Number);
  const next = new Date(Date.UTC(year, month - 1, date + delta));

  return next.toISOString().slice(0, 10);
}

export function formatDay(day: string): string {
  const [year, month, date] = day.split("-").map(Number);

  return new Date(Date.UTC(year, month - 1, date)).toLocaleDateString(
    "en-ZA",
    {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    }
  );
}

export function timeInSouthAfrica(value: string): string {
  return new Date(value).toLocaleTimeString("en-ZA", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Africa/Johannesburg",
  });
}

export function dateTimeInSouthAfrica(value: string): string {
  return new Date(value).toLocaleString("en-ZA", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Africa/Johannesburg",
  });
}
