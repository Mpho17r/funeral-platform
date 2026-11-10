"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import {
  AuthCard,
  Notice,
  authButtonClass,
  authInputClass,
} from "@/components/AuthCard";

function tokenFromLink(): string {
  const hash = window.location.hash.replace(/^#/, "");
  return new URLSearchParams(hash).get("token") ?? "";
}

export default function AcceptInvitationPage() {
  const [token, setToken] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setToken(tokenFromLink());
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("The two passwords are not the same.");
      return;
    }

    setLoading(true);
    try {
      const response = await api.post<{ message: string }>(
        "/auth/accept-invitation",
        { token, new_password: password },
      );
      setDone(response.data.message);
      window.history.replaceState(null, "", window.location.pathname);
    } catch (err) {
      setError(
        getApiErrorMessage(
          err,
          "We could not accept this invitation. Ask your administrator to send a new one.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  if (token === null) {
    return (
      <AuthCard title="Accept your LINDA invitation">
        <Loader2 className="animate-spin" />
      </AuthCard>
    );
  }

  if (done) {
    return (
      <AuthCard title="Your account is ready">
        <div className="space-y-4">
          <Notice kind="success">{done}</Notice>
          <Link
            href="/login"
            className={authButtonClass}
            style={{ backgroundColor: "var(--linda-navy)" }}
          >
            Sign in to LINDA
          </Link>
        </div>
      </AuthCard>
    );
  }

  if (!token) {
    return (
      <AuthCard title="Invitation link incomplete">
        <div className="space-y-4">
          <Notice kind="error">
            Open the invitation link exactly as it was emailed to you, or ask
            your administrator to send a new invitation.
          </Notice>
          <Link
            href="/login"
            className="text-sm font-medium underline underline-offset-4"
          >
            Return to sign in
          </Link>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Create your LINDA password"
      subtitle="Your administrator invited you to join their business. Choose a password only you know."
    >
      <form onSubmit={submit} className="space-y-5">
        <div>
          <label
            htmlFor="new-password"
            className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300"
          >
            New password
          </label>
          <input
            id="new-password"
            type={show ? "text" : "password"}
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={128}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className={authInputClass}
          />
        </div>
        <div>
          <label
            htmlFor="confirm-password"
            className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300"
          >
            Confirm password
          </label>
          <input
            id="confirm-password"
            type={show ? "text" : "password"}
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            className={authInputClass}
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
          <input
            type="checkbox"
            checked={show}
            onChange={(event) => setShow(event.target.checked)}
          />
          Show passwords
        </label>
        {error && <Notice kind="error">{error}</Notice>}
        <button
          type="submit"
          disabled={loading}
          className={authButtonClass}
          style={{ backgroundColor: "var(--linda-navy)" }}
        >
          {loading && <Loader2 size={18} className="animate-spin" />}
          Create password and activate account
        </button>
      </form>
    </AuthCard>
  );
}
