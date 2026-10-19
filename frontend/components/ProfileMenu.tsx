"use client";

import { CircleHelp, KeyRound, LogOut, Pencil, Settings } from "lucide-react";
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

  if (!user) {
    return null;
  }

  const primary = branding?.primary_color ?? undefined;

  function go(path: string) {
    setOpen(false);
    router.push(path);
  }

  function logout() {
    removeToken();
    router.push("/login");
  }

  const item =
    "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-[var(--fos-text-secondary)] transition hover:bg-[var(--fos-surface-muted)] hover:text-[var(--fos-text)]";

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
        <UserAvatar
          name={user.full_name}
          src={avatarUrl}
          size={36}
          color={primary}
        />

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

          <dl className="mx-1 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 rounded-xl bg-[var(--fos-surface-muted)] p-3 text-sm">
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
