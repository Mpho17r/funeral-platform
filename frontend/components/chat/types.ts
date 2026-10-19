export type Person = {
  id: string;
  name: string;
  role: string;
  job_title: string | null;
  status: "online" | "away" | "offline" | "checked_in";
};

export type Conversation = {
  id: string;
  kind: "direct" | "channel";
  title: string;
  description: string | null;
  other_user_id: string | null;
  participants: { id: string; name: string }[];
  last_message: {
    body: string;
    sender_name: string;
    created_at: string;
  } | null;
  last_message_at: string;
  unread: number;
};

export type Message = {
  id: string;
  conversation_id: string;
  sender_id: string | null;
  sender_name: string;
  kind: string;
  body: string;
  meta: Record<string, unknown> | null;
  reply_to_id: string | null;
  created_at: string;
  edited_at: string | null;
  deleted: boolean;
};

export function presenceColor(status: Person["status"] | undefined) {
  switch (status) {
    case "online":
    case "checked_in":
      return "#22c55e";
    case "away":
      return "#f59e0b";
    default:
      return "#94a3b8";
  }
}

export function presenceLabel(status: Person["status"] | undefined) {
  switch (status) {
    case "online":
      return "Online";
    case "checked_in":
      return "At work";
    case "away":
      return "Away";
    default:
      return "Offline";
  }
}
