export type Channel = "whatsapp" | "sms" | "email";

export type ReminderKind =
  | "payment_due_soon"
  | "payment_overdue"
  | "lapse_warning"
  | "lapsed";

export type MessageKind = ReminderKind | "custom";

export type MessageStatus = "queued" | "sent" | "cancelled";

export type CommunicationMessage = {
  id: string;
  member_id: string;
  member_name: string | null;
  membership_id: string | null;
  membership_number: string | null;
  kind: MessageKind;
  channel: Channel;
  recipient: string;
  subject: string | null;
  body: string;
  status: MessageStatus;
  action_url: string;
  created_at: string;
  sent_at: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  delivery_attempts: number;
  delivery_error: string | null;
  delivered_by: string | null;
};

export type MessageList = {
  items: CommunicationMessage[];
  total: number;
  counts: Record<MessageStatus, number>;
};

export type ReminderItem = {
  kind: ReminderKind;
  member_id: string;
  member_name: string;
  membership_id: string;
  membership_number: string;
  channel: Channel;
  recipient: string;
  subject: string;
  body: string;
};

export type SkippedItem = {
  kind: ReminderKind;
  member_id: string;
  member_name: string;
  membership_number: string;
  reason: "opted_out" | "no_contact";
};

export type ReminderPlan = {
  date: string;
  items: ReminderItem[];
  skipped: SkippedItem[];
  already_queued: number;
  disabled_kinds: ReminderKind[];
  counts: Record<string, number>;
};

export type ReminderGenerateResult = ReminderPlan & { created: number };

export type Template = {
  kind: ReminderKind;
  subject: string;
  body: string;
  is_active: boolean;
  is_default: boolean;
};

export type TemplateList = {
  templates: Template[];
  placeholders: { name: string; description: string }[];
};

export type Preference = {
  member_id: string;
  preferred_channel: Channel;
  opted_out: boolean;
  opted_out_at: string | null;
  opt_out_reason: string | null;
};

export const KIND_LABELS: Record<MessageKind, string> = {
  payment_due_soon: "Due soon",
  payment_overdue: "Overdue",
  lapse_warning: "Lapse warning",
  lapsed: "Lapsed",
  custom: "Message",
};

export const KIND_STYLE: Record<MessageKind, string> = {
  payment_due_soon: "bg-blue-100 text-blue-700",
  payment_overdue: "bg-amber-100 text-amber-800",
  lapse_warning: "bg-orange-100 text-orange-800",
  lapsed: "bg-red-100 text-red-700",
  custom: "bg-slate-200 text-slate-700",
};

export const KIND_HELP: Record<ReminderKind, string> = {
  payment_due_soon:
    "A contribution falls due in the next few days.",
  payment_overdue:
    "A contribution is past its due date and the cover has not lapsed.",
  lapse_warning:
    "The membership is about to lapse because of unpaid contributions.",
  lapsed: "The membership has just lapsed.",
};

export const CHANNEL_LABELS: Record<Channel, string> = {
  whatsapp: "WhatsApp",
  sms: "SMS",
  email: "Email",
};

export const CHANNELS: Channel[] = ["whatsapp", "sms", "email"];

export const SKIP_REASON: Record<SkippedItem["reason"], string> = {
  opted_out: "Opted out of messages",
  no_contact: "No usable phone number or email",
};

export function openLabel(channel: Channel): string {
  return `Open in ${CHANNEL_LABELS[channel]}`;
}

// A phone number is stored as digits only, so show it with a + again.
export function formatRecipient(message: {
  channel: Channel;
  recipient: string;
}): string {
  return message.channel === "email"
    ? message.recipient
    : `+${message.recipient}`;
}

export function formatWhen(value: string): string {
  return new Date(value).toLocaleString("en-ZA", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Africa/Johannesburg",
  });
}
