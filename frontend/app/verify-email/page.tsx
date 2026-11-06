"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

import api from "@/lib/api";
import { getToken } from "@/lib/auth";
import { getApiErrorMessage } from "@/lib/format";
import { AuthCard, Notice, authButtonClass } from "@/components/AuthCard";

type State =
  | { kind: "working" }
  | { kind: "ok"; message: string }
  | { kind: "bad"; message: string };

export default function VerifyEmailPage() {
  const [state, setState] = useState<State>({ kind: "working" });
  const started = useRef(false);

  useEffect(() => {
    // Strict mode runs effects twice in development; one use of a
    // single-use link is enough.
    if (started.current) {
      return;
    }

    started.current = true;

    const hash = window.location.hash.replace(/^#/, "");
    const token = new URLSearchParams(hash).get("token") ?? "";

    if (!token) {
      setState({
        kind: "bad",
        message: "Open the link exactly as it was emailed to you.",
      });
      return;
    }

    api
      .post<{ message: string }>("/auth/verify-email", { token })
      .then((response) => {
        setState({ kind: "ok", message: response.data.message });
        window.history.replaceState(null, "", window.location.pathname);
      })
      .catch((err) =>
        setState({
          kind: "bad",
          message: getApiErrorMessage(
            err,
            "We could not confirm that address. Try again.",
          ),
        }),
      );
  }, []);

  const signedIn = typeof window !== "undefined" && !!getToken();

  return (
    <AuthCard title="Confirm your email">
      {state.kind === "working" && (
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <Loader2 className="animate-spin" size={18} />
          Confirming your address…
        </div>
      )}

      {state.kind === "ok" && (
        <div className="space-y-4">
          <Notice kind="success">{state.message}</Notice>
          <Link
            href={signedIn ? "/dashboard" : "/login"}
            className={authButtonClass}
            style={{ backgroundColor: "var(--linda-navy)" }}
          >
            {signedIn ? "Go to LINDA" : "Sign in"}
          </Link>
        </div>
      )}

      {state.kind === "bad" && (
        <div className="space-y-3">
          <Notice kind="error">{state.message}</Notice>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Sign in and use the banner at the top to send yourself a new link.
          </p>
        </div>
      )}
    </AuthCard>
  );
}
