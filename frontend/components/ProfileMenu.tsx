"use client";

import { CircleHelp, Coffee, KeyRound, Loader2, LogIn, LogOut, Pencil, Settings, Utensils } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { useBranding } from "@/components/BrandingProvider";
import {
  roleLabel,
  titleOf,
  useCurrentUser,
} from "@/components/CurrentUserProvider";
import { ChangePasswordDialog } from "@/components/PasswordDialogs";
import { ProfileDialog } from "@/components/ProfileDialog";
import { UserAvatar } from "@/components/UserAvatar";
import { removeToken } from "@/lib/auth";
import api from "@/lib/api";

type AttendanceMe = {
  attendance: { checked_in_at: string; status: string } | null;
  current_break: { break_type: "tea" | "lunch"; started_at: string } | null;
  presence: "online" | "away" | "busy" | "offline" | "checked_in";
};

function formatSince(value: string | null | undefined) {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleDateString("en-GB", {
    month: "long",
    year: "numeric",
  });
}

/** Who is signed in, at the top right of every screen: name, title and
 *  photo, with their details and the things a person does about themself. */
export function ProfileMenu() {
  const router = useRouter();
  const { user, avatarUrl } = useCurrentUser();
  const { branding } = useBranding();

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [notice, setNotice] = useState("");
  const [attendance, setAttendance] = useState<AttendanceMe | null>(null);
  const [attendanceLoading, setAttendanceLoading] = useState(false);
  const [attendanceAction, setAttendanceAction] = useState(false);
  const [reminderOpen, setReminderOpen] = useState(false);
  const [attendanceError, setAttendanceError] = useState("");
  const [presenceStatus, setPresenceStatus] = useState<"online" | "away" | "busy" | "offline">("online");
  const [presenceSaving, setPresenceSaving] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [menuPosition, setMenuPosition] = useState({ top: 64, right: 16 });

  useEffect(() => {
    if (!open) {
      return;
    }

    function onPointer(event: MouseEvent) {
      const target = event.target as Node;
      if (
        !root.current?.contains(target) &&
        !menu.current?.contains(target)
      ) {
        setOpen(false);
      }
    }

    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);

    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    if (!notice) {
      return;
    }

    const timer = setTimeout(() => setNotice(""), 5000);

    return () => clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setAttendanceLoading(true);
    api.get<AttendanceMe>("/attendance/me")
      .then(async (response) => {
        if (cancelled) return;
        setAttendance(response.data);
        setPresenceStatus(response.data.current_break ? "away" : response.data.presence === "busy" ? "busy" : "online");
        if (!response.data.attendance && typeof window !== "undefined") {
          const reminderKey = `funeralos-checkin-reminded-${user.user_id}`;
          if (!sessionStorage.getItem(reminderKey)) {
            setReminderOpen(true);
            sessionStorage.setItem(reminderKey, "1");
          }
        }
        try {
          const mine = await api.get<{ status: string }>("/presence/me");
          if (cancelled) return;
          const current = mine.data.status;
          if (current === "busy") {
            setPresenceStatus("busy");
          } else if (current === "offline" || current === "checked_in") {
            const next = response.data.current_break ? "away" : "online";
            await api.patch("/presence/me", { status: next });
            if (!cancelled) setPresenceStatus(next);
          } else {
            setPresenceStatus(response.data.current_break ? "away" : current === "away" ? "away" : "online");
          }
        } catch {
          // The profile remains usable if presence permissions are unavailable.
        }
      })
      .catch(() => {
        // Attendance can be unavailable for a short period; keep the profile usable.
      })
      .finally(() => {
        if (!cancelled) setAttendanceLoading(false);
      });
    return () => { cancelled = true; };
  }, [user?.user_id]);

  async function runAttendanceAction(action: "check-in" | "check-out" | "start-tea" | "start-lunch" | "end-break") {
    setAttendanceAction(true);
    setAttendanceError("");
    try {
      if (action === "check-in") await api.post("/attendance/check-in");
      if (action === "check-out") await api.post("/attendance/check-out");
      if (action === "start-tea") await api.post("/attendance/breaks/start", { break_type: "tea" });
      if (action === "start-lunch") await api.post("/attendance/breaks/start", { break_type: "lunch" });
      if (action === "end-break") await api.post("/attendance/breaks/end");
      const response = await api.get<AttendanceMe>("/attendance/me");
      setAttendance(response.data);
      setPresenceStatus(response.data.current_break ? "away" : response.data.presence === "busy" ? "busy" : response.data.attendance ? "online" : "online");
      setReminderOpen(false);
      setOpen(false);
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
      setAttendanceError(typeof detail === "string" ? detail : "We couldn't update your shift. Please try again.");
    } finally {
      setAttendanceAction(false);
    }
  }

  if (!user) {
    return null;
  }

  const primary = branding?.primary_color ?? undefined;

  function go(path: string) {
    setOpen(false);
    router.push(path);
  }

  async function logout() {
    try {
      await api.patch("/presence/me", { status: "offline" });
    } catch {
      // Sign-out must still work if the presence service is unavailable.
    } finally {
      removeToken();
      router.push("/login");
    }
  }

  const item =
    "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-[var(--fos-text-secondary)] transition hover:bg-[var(--fos-surface-muted)] hover:text-[var(--fos-text)]";

  async function changePresence(next: "online" | "away" | "busy") {
    setPresenceSaving(true);
    setAttendanceError("");
    try {
      await api.patch("/presence/me", { status: next });
      setPresenceStatus(next);
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
      setAttendanceError(typeof detail === "string" ? detail : "Your availability could not be updated.");
    } finally {
      setPresenceSaving(false);
    }
  }

  return (
    <div ref={root} className="relative z-[110]">
      <button
        type="button"
        ref={trigger}
        onClick={(event) => {
          if (open) {
            setOpen(false);
            return;
          }
          const rect = event.currentTarget.getBoundingClientRect();
          setMenuPosition({
            top: rect.bottom + 8,
            right: Math.max(16, window.innerWidth - rect.right),
          });
          setOpen(true);
        }}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Your profile and account"
        className="flex items-center gap-3 rounded-xl py-1 pl-1 pr-2 transition hover:bg-[var(--fos-surface-muted)] sm:pr-3"
      >
        <span className="relative inline-flex">
          <UserAvatar
            name={user.full_name}
            src={avatarUrl}
            size={36}
            color={primary}
          />
          <span
            title={attendance?.current_break ? "Away — on break" : "Online"}
            className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-[var(--fos-surface)] ${attendance?.current_break || presenceStatus === "away" ? "bg-amber-400" : presenceStatus === "busy" ? "bg-red-500" : presenceStatus === "offline" ? "bg-slate-400" : "bg-emerald-500"}`}
          />
        </span>

        <span className="hidden min-w-0 text-left sm:block">
          <span className="block max-w-[11rem] truncate text-sm font-semibold leading-tight text-[var(--fos-text)]">
            {user.full_name ?? "Signed in"}
          </span>
          <span className="block max-w-[11rem] truncate text-xs leading-tight text-[var(--fos-text-muted)]">
            {titleOf(user)}
          </span>
        </span>
      </button>

      {open && typeof document !== "undefined" && createPortal(
        <div
          ref={menu}
          role="menu"
          style={{ top: menuPosition.top, right: menuPosition.right }}
          className="fixed z-[9999] max-h-[calc(100vh-1rem)] w-80 max-w-[calc(100vw-2rem)] overflow-y-auto rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-2 shadow-xl"
        >
          <div className="flex items-center gap-3 px-3 py-3">
            <UserAvatar
              name={user.full_name}
              src={avatarUrl}
              size={56}
              color={primary}
            />

            <div className="min-w-0">
              <p className="truncate font-semibold text-[var(--fos-text)]">
                {user.full_name ?? "Signed in"}
              </p>
              <p className="truncate text-sm text-[var(--fos-text-muted)]">
                {titleOf(user)}
              </p>
            </div>
          </div>

          <div className="mx-1 rounded-xl bg-[var(--fos-surface-muted)] p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">Availability</p>
            <div className="mt-2 grid grid-cols-3 gap-1.5">
              {([
                ["online", "Online", "bg-emerald-500"],
                ["away", "Away", "bg-amber-400"],
                ["busy", "Busy", "bg-red-500"],
              ] as const).map(([value, label, dot]) => (
                <button key={value} type="button" disabled={presenceSaving || (Boolean(attendance?.current_break) && value !== "away")} onClick={() => void changePresence(value)} className={`flex items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-xs font-medium transition disabled:opacity-50 ${presenceStatus === value ? "border-[var(--fos-primary)] bg-[var(--fos-surface)] text-[var(--fos-text)]" : "border-transparent text-[var(--fos-text-muted)] hover:bg-[var(--fos-surface)]"}`}>
                  <span className={`h-2 w-2 rounded-full ${dot}`} />{label}
                </button>
              ))}
            </div>
            {attendance?.current_break && <p className="mt-2 text-xs text-[var(--fos-text-muted)]">You're on a break, so your status stays Away until you return.</p>}
          </div>

          <div className="mx-1 mt-1 rounded-xl border border-[var(--fos-border)] p-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--fos-text-muted)]">My shift</p>
                <p className="mt-1 text-sm font-medium text-[var(--fos-text)]">
                  {attendanceLoading ? "Checking shift…" : attendance?.current_break ? (attendance.current_break.break_type === "tea" ? "On tea break · Away" : "On lunch break · Away") : attendance?.attendance ? "On shift · Online" : "Not checked in"}
                </p>
              </div>
              {attendanceLoading ? <Loader2 size={16} className="animate-spin text-[var(--fos-text-muted)]" /> : null}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {!attendance?.attendance ? (
                <button type="button" disabled={attendanceAction || attendanceLoading} onClick={() => void runAttendanceAction("check-in")} className="inline-flex items-center gap-2 rounded-lg bg-[var(--fos-primary)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60">
                  {attendanceAction ? <Loader2 size={15} className="animate-spin" /> : <LogIn size={15} />} Clock in
                </button>
              ) : attendance.current_break ? (
                <button type="button" disabled={attendanceAction} onClick={() => void runAttendanceAction("end-break")} className="inline-flex items-center gap-2 rounded-lg bg-[var(--fos-primary)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60">
                  {attendanceAction ? <Loader2 size={15} className="animate-spin" /> : <Coffee size={15} />} End break
                </button>
              ) : (
                <>
                  <button type="button" disabled={attendanceAction} onClick={() => void runAttendanceAction("start-tea")} className="inline-flex items-center gap-2 rounded-lg border border-[var(--fos-border)] px-3 py-2 text-sm font-medium text-[var(--fos-text)] disabled:opacity-60"><Coffee size={15} /> Tea break</button>
                  <button type="button" disabled={attendanceAction} onClick={() => void runAttendanceAction("start-lunch")} className="inline-flex items-center gap-2 rounded-lg border border-[var(--fos-border)] px-3 py-2 text-sm font-medium text-[var(--fos-text)] disabled:opacity-60"><Utensils size={15} /> Lunch</button>
                  <button type="button" disabled={attendanceAction} onClick={() => void runAttendanceAction("check-out")} className="inline-flex items-center gap-2 rounded-lg border border-[var(--fos-border)] px-3 py-2 text-sm font-medium text-[var(--fos-text)] disabled:opacity-60"><LogOut size={15} /> Clock out</button>
                </>
              )}
            </div>
            {attendanceError && <p role="alert" className="mt-2 text-xs text-red-600">{attendanceError}</p>}
          </div>

          <dl className="mx-1 mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 rounded-xl bg-[var(--fos-surface-muted)] p-3 text-sm">
            <dt className="text-[var(--fos-text-muted)]">Email</dt>
            <dd className="truncate text-right text-[var(--fos-text)]">
              {user.email ?? "—"}
            </dd>

            <dt className="text-[var(--fos-text-muted)]">Access</dt>
            <dd className="text-right text-[var(--fos-text)]">
              {roleLabel(user.role)}
            </dd>

            <dt className="text-[var(--fos-text-muted)]">Branch</dt>
            <dd className="truncate text-right text-[var(--fos-text)]">
              {user.branch_name ?? "All branches"}
            </dd>

            <dt className="text-[var(--fos-text-muted)]">Business</dt>
            <dd className="truncate text-right text-[var(--fos-text)]">
              {user.business_name ?? branding?.name ?? "—"}
            </dd>

            <dt className="text-[var(--fos-text-muted)]">With us since</dt>
            <dd className="text-right text-[var(--fos-text)]">
              {formatSince(user.member_since)}
            </dd>
          </dl>

          <div className="mt-2 space-y-0.5">
            <button
              type="button"
              role="menuitem"
              className={item}
              onClick={() => {
                setOpen(false);
                setEditing(true);
              }}
            >
              <Pencil size={16} />
              Edit profile and photo
            </button>

            <button
              type="button"
              role="menuitem"
              className={item}
              onClick={() => {
                setOpen(false);
                setChangingPassword(true);
              }}
            >
              <KeyRound size={16} />
              Change password
            </button>

            <button
              type="button"
              role="menuitem"
              className={item}
              onClick={() => go("/settings")}
            >
              <Settings size={16} />
              Settings
            </button>

            <button
              type="button"
              role="menuitem"
              className={item}
              onClick={() => go("/help")}
            >
              <CircleHelp size={16} />
              Guide
            </button>

            <div className="my-1 border-t border-[var(--fos-border)]" />

            <button
              type="button"
              role="menuitem"
              className={item}
              onClick={logout}
            >
              <LogOut size={16} />
              Log out
            </button>
          </div>
        </div>,
        document.body,
      )}

      {editing && <ProfileDialog onClose={() => setEditing(false)} />}

      {changingPassword && (
        <ChangePasswordDialog
          onClose={() => setChangingPassword(false)}
          onDone={(message) => {
            setChangingPassword(false);
            setNotice(message);
          }}
        />
      )}

      {reminderOpen && !attendance?.attendance && (
        <div role="dialog" aria-label="Clock-in reminder" className="fixed right-4 top-20 z-[9998] w-[min(22rem,calc(100vw-2rem))] rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-4 shadow-xl">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-800"><LogIn size={18} /></span>
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-[var(--fos-text)]">Don't forget to clock in</p>
              <p className="mt-1 text-sm text-[var(--fos-text-muted)]">You're signed in but haven't started your shift yet.</p>
              <div className="mt-3 flex items-center gap-2">
                <button type="button" disabled={attendanceAction} onClick={() => void runAttendanceAction("check-in")} className="rounded-lg bg-[var(--fos-primary)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60">Clock in</button>
                <button type="button" onClick={() => setReminderOpen(false)} className="rounded-lg px-3 py-2 text-sm text-[var(--fos-text-muted)] hover:bg-[var(--fos-surface-muted)]">Remind me later</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {notice && (
        <div
          role="status"
          className="fixed right-4 top-16 z-50 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 shadow-lg"
        >
          {notice}
        </div>
      )}
    </div>
  );
}
