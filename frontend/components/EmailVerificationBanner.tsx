"use client";

import { useState } from "react";
import { MailWarning, X } from "lucide-react";

import api from "@/lib/api";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { getApiErrorMessage } from "@/lib/format";

const DISMISS_KEY = "linda_hide_verify_banner";

function dismissedBefore(): boolean {
  try {
    return sessionStorage.getItem(DISMISS_KEY) === "1";
  } catch {
    return false;
  }
}

/**
 * Asks people who have not confirmed their email address to do so. It does
 * not block anything: a server without email set up could never verify
 * anyone. Confirming matters because "forgot password" goes to this address.
 */
export function EmailVerificationBanner() {
  const { user } = useCurrentUser();
  const [hidden, setHidden] = useState(dismissedBefore);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  if (!user || user.email_verified !== false || hidden) {
    return null;
  }

  async function resend() {
    setBusy(true);
    setNote("");

    try {
      const response = await api.post<{ status: string; message?: string }>(
        "/auth/resend-verification",
      );
      const { status, message } = response.data;

      setNote(
        status === "sent" || status === "email_not_set_up"
          ? (message ?? "")
          : "Your address is already confirmed. Refresh the page.",
      );
    } catch (err) {
      setNote(getApiErrorMessage(err, "We could not send that. Try again."));
    } finally {
      setBusy(false);
    }
  }

  function dismiss() {
    try {
      sessionStorage.setItem(DISMISS_KEY, "1");
    } catch {
      // Remembering is a convenience only.
    }
    setHidden(true);
  }

  return (
    <div
      role="status"
      className="mx-4 mt-4 flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-200 sm:mx-6"
    >
      <MailWarning size={18} className="mt-0.5 shrink-0" />

      <div className="flex-1">
        <p>
          <span className="font-semibold">Confirm your email address.</span>{" "}
          If you forget your password, the reset link goes to{" "}
          <span className="font-medium">{user.email}</span>.
        </p>

        {note && <p className="mt-1 font-medium">{note}</p>}

        <button
          type="button"
          onClick={() => void resend()}
          disabled={busy}
          className="mt-2 rounded-md border border-amber-400 bg-white px-3 py-1 font-medium text-amber-900 hover:bg-amber-100 disabled:opacity-60"
        >
          {busy ? "Sending…" : "Send me the link"}
        </button>
      </div>

      <button
        type="button"
        aria-label="Hide this message"
        onClick={dismiss}
        className="rounded p-1 hover:bg-amber-100 dark:hover:bg-amber-900"
      >
        <X size={16} />
      </button>
    </div>
  );
}
