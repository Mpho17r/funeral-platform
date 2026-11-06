"use client";

import { FormEvent, useState } from "react";
import { Loader2 } from "lucide-react";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import {
  AuthCard,
  Notice,
  authButtonClass,
  authInputClass,
} from "@/components/AuthCard";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await api.post<{ message: string }>(
        "/auth/forgot-password",
        { email: email.trim() },
      );

      setMessage(response.data.message);
    } catch (err) {
      setError(
        getApiErrorMessage(err, "We could not send that. Please try again."),
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthCard
      title="Forgot your password?"
      subtitle="Enter the email address you sign in with and we will send you a link to choose a new one."
    >
      {message ? (
        <div className="space-y-3">
          <Notice kind="success">{message}</Notice>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Nothing arrived? Check your spam folder, or ask your administrator
            to set a new password for you.
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          <div>
            <label
              htmlFor="email"
              className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300"
            >
              Email address
            </label>
            <input
              id="email"
              type="email"
              inputMode="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@example.com"
              className={authInputClass}
            />
          </div>

          {error && <Notice kind="error">{error}</Notice>}

          <button
            type="submit"
            disabled={loading}
            className={authButtonClass}
            style={{ backgroundColor: "var(--linda-navy)" }}
          >
            {loading && <Loader2 size={18} className="animate-spin" />}
            Send reset link
          </button>
        </form>
      )}
    </AuthCard>
  );
}
