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
  /** Organisation and branch channels are kept in step with the team. */
  system?: boolean;
  scope?: "organisation" | "branch" | null;
  other_user_id: string | null;
  participants: { id: string; name: string }[];
  last_message: {
    body: string;
    sender_name: string;
    created_at: string;
  } | null;
  last_message_at: string;
  unread: number;
  mentioned: boolean;
};

export type Reaction = { emoji: string; count: number; mine: boolean };

export type Attachment = {
  id: string;
  filename: string;
  media_type: string;
  size_bytes: number;
  is_image: boolean;
};

export type MeetingInvitee = {
  id: string;
  name: string;
  response: "pending" | "accepted" | "declined";
};

export type Meeting = {
  id: string;
  title: string;
  description: string | null;
  starts_at: string;
  ends_at: string;
  join_url: string | null;
  organizer_id: string | null;
  organizer_name: string;
  conversation_id: string | null;
  cancelled: boolean;
  my_response: "pending" | "accepted" | "declined" | null;
  is_organizer: boolean;
  invitees: MeetingInvitee[];
  conflicts?: { user_name: string; title: string }[];
};

export const REACTIONS = ["👍", "❤️", "😂", "🙏", "✅", "😮"];

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export type Message = {
  id: string;
  conversation_id: string;
  sender_id: string | null;
  sender_name: string;
  kind: string;
  body: string;
  meta: Record<string, unknown> | null;
  mention_ids: string[];
  reactions: Reaction[];
  attachments: Attachment[];
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
