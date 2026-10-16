export type MortuaryLocation = {
  id: string;
  branch_id: string | null;
  name: string;
  kind: string;
  capacity: number | null;
  notes: string | null;
  is_active: boolean;
  occupied: number;
};

export type Remains = {
  id: string;
  case_id: string;
  tag_number: string;
  status: "in_custody" | "released";
  received_at: string;
  received_from_type: string;
  received_from: string | null;
  collected_by_name: string | null;
  vehicle_resource_id: string | null;
  condition_notes: string | null;
  belongings: string | null;
  current_location_id: string | null;
  cooled_at: string | null;
  identified_at: string | null;
  identified_by_name: string | null;
  identified_relationship: string | null;
  released_at: string | null;
  released_to_name: string | null;
  released_to_id_number: string | null;
  released_to_relationship: string | null;
  release_override_reason: string | null;
};

export type CustodyEvent = {
  id: string;
  event_type: string;
  from_location_id: string | null;
  to_location_id: string | null;
  procedure: string | null;
  temperature_c: string | null;
  occurred_at: string;
  notes: string | null;
};

export type RemainsDetail = {
  remains: Remains;
  cooling: {
    cooled: boolean;
    cooling_due_at: string | null;
    cooling_overdue: boolean;
  };
  release_blockers: string[];
  events: CustodyEvent[];
};

export type BoardEntry = {
  remains_id: string;
  case_id: string;
  case_number: string;
  deceased_full_name: string;
  tag_number: string;
  location_id: string | null;
  location_name: string | null;
  received_at: string;
  identified: boolean;
  cooled: boolean;
  cooling_due_at: string | null;
  cooling_overdue: boolean;
};

export type Board = {
  in_custody: number;
  cooling_overdue: number;
  entries: BoardEntry[];
  locations: MortuaryLocation[];
};

export const LOCATION_KINDS = [
  { value: "fridge", label: "Fridge" },
  { value: "cold_room", label: "Cold room" },
  { value: "preparation_room", label: "Preparation room" },
  { value: "chapel_of_rest", label: "Chapel of rest" },
  { value: "other", label: "Other" },
];

export const RECEIVED_FROM = [
  { value: "home", label: "Home" },
  { value: "hospital", label: "Hospital or clinic" },
  { value: "state_mortuary", label: "State mortuary" },
  { value: "scene", label: "Scene of death" },
  { value: "other", label: "Other" },
];

export const PROCEDURES = [
  { value: "washed", label: "Washed" },
  { value: "embalmed", label: "Embalmed" },
  { value: "dressed", label: "Dressed" },
  { value: "other", label: "Other" },
];

export const EVENT_LABELS: Record<string, string> = {
  received: "Taken into care",
  moved: "Moved",
  prepared: "Prepared",
  identified: "Identified",
  temperature: "Temperature taken",
  released: "Released",
  note: "Note",
};

export function labelOf(
  options: { value: string; label: string }[],
  value: string | null
): string {
  return options.find((o) => o.value === value)?.label ?? "—";
}

export function formatDateTime(value: string): string {
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
