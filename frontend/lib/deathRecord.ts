export type DeathRecord = {
  id: string;
  case_id: string;
  deceased_id_type: string;
  deceased_id_number: string | null;
  time_of_death: string | null;
  place_of_death_type: string | null;
  place_of_death: string | null;
  manner_of_death: string;
  unnatural_cause: string | null;
  cause_of_death: string | null;
  certifier_name: string | null;
  forensic_status: string;
  police_case_number: string | null;
  infectious_remains: boolean;
  disposal_method: string;
  informant_name: string | null;
  informant_relationship: string | null;
  informant_phone: string | null;
  informant_id_number: string | null;
  informant_id_warning?: string | null;
  notes: string | null;
};

export type PaperworkItem = {
  id: string;
  case_id: string;
  item_type: string;
  label: string;
  required: boolean;
  status: "pending" | "obtained" | "not_applicable";
  reference_number: string | null;
  obtained_on: string | null;
  document_id: string | null;
  notes: string | null;
};

export type PaperworkSummary = {
  required_total: number;
  required_done: number;
  outstanding: string[];
  ready: boolean;
};

export type Paperwork = {
  items: PaperworkItem[];
  summary: PaperworkSummary;
};

export const ID_TYPES = [
  { value: "sa_id", label: "South African ID" },
  { value: "passport", label: "Passport" },
  { value: "other", label: "Other" },
];

export const PLACE_TYPES = [
  { value: "home", label: "Home" },
  { value: "hospital", label: "Hospital or clinic" },
  { value: "public_place", label: "Public place" },
  { value: "other", label: "Other" },
];

export const MANNERS = [
  { value: "pending", label: "Not yet known" },
  { value: "natural", label: "Natural" },
  { value: "unnatural", label: "Unnatural" },
];

// Decides which cover waiting period applies: a homicide is treated like
// an accident, a suicide has its own period.
export const UNNATURAL_CAUSES = [
  { value: "", label: "Not yet known" },
  { value: "accident", label: "Accident" },
  { value: "suicide", label: "Suicide" },
  { value: "homicide", label: "Homicide" },
  { value: "undetermined", label: "Undetermined" },
];

export const FORENSIC_STATUSES = [
  { value: "not_applicable", label: "Not applicable" },
  { value: "referred", label: "Referred to forensic pathology" },
  { value: "post_mortem_done", label: "Post-mortem done" },
  { value: "released", label: "Released" },
];

export const DISPOSALS = [
  { value: "burial", label: "Burial" },
  { value: "cremation", label: "Cremation" },
  { value: "repatriation", label: "Repatriation" },
];

export function labelFor(
  options: { value: string; label: string }[],
  value: string | null
): string {
  return (
    options.find((option) => option.value === value)?.label ?? "—"
  );
}


/** A reason to re-check a 13-digit South African ID number, or null.
 *  Same rule as the server: 13 digits, a real date of birth, citizenship
 *  digit 0 or 1, and the Luhn check digit. Anything else is not judged. */
export function saIdProblem(value: string): string | null {
  const n = value.replace(/[\s-]/g, "");
  if (!/^\d{13}$/.test(n)) return null;
  const month = Number(n.slice(2, 4));
  const day = Number(n.slice(4, 6));
  if (month < 1 || month > 12 || day < 1 || day > 31) {
    return "The ID number does not start with a valid date of birth.";
  }
  if (n[10] !== "0" && n[10] !== "1") {
    return "The ID number has an invalid citizenship digit.";
  }
  let total = 0;
  [...n].reverse().forEach((ch, i) => {
    let d = Number(ch);
    if (i % 2 === 1) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    total += d;
  });
  return total % 10 === 0
    ? null
    : "The last digit does not match the rest of the number. Please re-check it.";
}
