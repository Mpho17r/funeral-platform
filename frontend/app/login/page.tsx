"use client";

import {
  FormEvent,
  useEffect,
  useState,
} from "react";
import Link from "next/link";

import { useRouter } from "next/navigation";

import {
  BarChart3,
  Briefcase,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Sparkles,
  Users,
  Workflow,
} from "lucide-react";

import api from "@/lib/api";
import { saveToken } from "@/lib/auth";
import { LindaLockup, LindaMark } from "@/components/LindaLogo";
import {
  PLATFORM_OWNER,
  PLATFORM_SLOGAN,
} from "@/lib/platform";

const HIGHLIGHTS = [
  { icon: Briefcase, label: "Business Management" },
  { icon: Users, label: "People and Customers" },
  { icon: BarChart3, label: "Finance and Performance" },
  { icon: Workflow, label: "Operations and Workflows" },
  { icon: Sparkles, label: "Intelligent Assistance" },
];

const ROTATING_MESSAGES = [
  "One business. One connected workspace.",
  "Clarity in every operation.",
  "Better decisions start with better visibility.",
  "Your business operations, working in harmony.",
  "Spend less time managing. More time growing.",
];

/** A quiet line that changes every few seconds. Still when motion is reduced. */
function RotatingMessage() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const reduce = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (reduce) return;

    const timer = window.setInterval(
      () => setIndex((i) => (i + 1) % ROTATING_MESSAGES.length),
      5000,
    );
    return () => window.clearInterval(timer);
  }, []);

  return (
    <p
      key={index}
      aria-live="off"
      className="animate-[linda-fade_700ms_ease-out] text-sm font-medium"
      style={{ color: "var(--linda-gold)" }}
    >
      {ROTATING_MESSAGES[index]}
    </p>
  );
}

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [registrationOpen, setRegistrationOpen] = useState(false);
  const [verificationNotice, setVerificationNotice] = useState("");
  const [resendingVerification, setResendingVerification] = useState(false);

  useEffect(() => {
    api
      .get<{ open: boolean }>("/auth/registration-status")
      .then((r) => setRegistrationOpen(r.data.open))
      .catch(() => setRegistrationOpen(false));
  }, []);

  async function resendVerification() {
    setResendingVerification(true);
    try {
      const response = await api.post("/auth/resend-verification", { email });
      setVerificationNotice(response.data.message || "If the account needs verification, a link has been sent.");
    } catch {
      setVerificationNotice("We couldn't send the link right now. Please try again later.");
    } finally {
      setResendingVerification(false);
    }
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      const response = await api.post("/auth/login", {
        email,
        password,
      });

      saveToken(response.data.access_token);

      router.push("/dashboard");
    } catch (err) {
      const detail = (
        err as { response?: { data?: { detail?: unknown } } }
      ).response?.data?.detail;

      if (typeof detail === "string" && detail) {
        setError(detail);
        setVerificationNotice(
          detail.toLowerCase().includes("verify your email") ? "needed" : "",
        );
      } else {
        setError(
          "We couldn't reach the server. Check your connection and try again.",
        );
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-[var(--linda-grey)] dark:bg-slate-950 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      {/* BRAND PANEL */}
      <aside
        className="relative hidden overflow-hidden text-white lg:flex lg:flex-col lg:justify-between lg:p-14"
        style={{ backgroundColor: "var(--linda-navy)" }}
      >
        {/* Connected nodes: one quiet motif, nothing else competes */}
        <svg
          aria-hidden="true"
          viewBox="0 0 600 600"
          className="pointer-events-none absolute -bottom-32 -right-32 h-[620px] w-[620px]"
          fill="none"
          stroke="#D6A85F"
        >
          <path
            d="M120 80 V420 H430"
            strokeWidth="34"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.07"
          />
          {[
            [120, 80],
            [120, 250],
            [120, 420],
            [275, 420],
            [430, 420],
          ].map(([x, y]) => (
            <circle
              key={`${x}-${y}`}
              cx={x}
              cy={y}
              r="9"
              fill="#D6A85F"
              strokeWidth="0"
              opacity="0.22"
            />
          ))}
        </svg>

        <LindaLockup markSize={44} size="md" className="relative text-white" />

        <div className="relative max-w-lg">
          <h1 className="text-5xl font-semibold leading-[1.08] tracking-tight">
            Run your business. Don&apos;t let your business run you.
          </h1>

          <p className="mt-6 max-w-md text-base leading-relaxed text-white/70">
            From daily operations to long-term growth, LINDA brings your
            entire business together in one intelligent workspace.
          </p>

          <ul className="mt-10 grid max-w-md gap-3">
            {HIGHLIGHTS.map(({ icon: Icon, label }) => (
              <li
                key={label}
                className="flex items-center gap-3 text-sm text-white/85"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.07] ring-1 ring-white/10">
                  <Icon size={16} style={{ color: "var(--linda-gold)" }} />
                </span>
                {label}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative space-y-4">
          <div
            aria-hidden="true"
            className="h-px w-24"
            style={{ backgroundColor: "var(--linda-gold)" }}
          />
          <RotatingMessage />
        </div>
      </aside>

      {/* FORM */}
      <section className="flex flex-col px-6 py-10 sm:px-10">
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-sm">
            {/* Brand, shown when the side panel is hidden */}
            <div className="mb-10 flex items-center gap-3 text-[var(--linda-navy)] dark:text-white lg:hidden">
              <LindaMark size={40} />
              <span className="text-lg font-semibold tracking-[0.22em]">
                LINDA
              </span>
            </div>

            <p
              className="hidden text-xs font-semibold uppercase tracking-[0.14em] lg:block"
              style={{ color: "var(--linda-gold-text)" }}
            >
              LINDA
            </p>

            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">
              Welcome back
            </h2>

            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              Sign in to your business workspace.
            </p>

          <form
            onSubmit={handleSubmit}
            className="mt-8 space-y-5"
          >
            <div>
              <label
                htmlFor="email"
                className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300"
              >
                Email address
              </label>

              <input
                id="email"
                name="email"
                type="email"
                inputMode="email"
                autoComplete="username"
                value={email}
                onChange={(event) =>
                  setEmail(event.target.value)
                }
                placeholder="name@example.com"
                required
                className="h-12 w-full rounded-lg border border-slate-300 bg-white px-4 text-base text-slate-900 transition dark:border-slate-700 dark:bg-slate-900 dark:text-white"
              />
            </div>

            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-slate-700 dark:text-slate-300"
                >
                  Password
                </label>

                <button
                  type="button"
                  onClick={() =>
                    router.push("/forgot-password")
                  }
                  className="rounded text-sm font-medium text-slate-600 underline-offset-4 hover:text-slate-900 hover:underline dark:text-slate-400 dark:hover:text-white"
                >
                  Forgot password?
                </button>
              </div>

              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) =>
                    setPassword(event.target.value)
                  }
                  required
                  className="h-12 w-full rounded-lg border border-slate-300 bg-white pl-4 pr-12 text-base text-slate-900 transition dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                />

                <button
                  type="button"
                  aria-label={
                    showPassword
                      ? "Hide password"
                      : "Show password"
                  }
                  aria-pressed={showPassword}
                  onClick={() =>
                    setShowPassword((current) => !current)
                  }
                  className="absolute right-1.5 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-md text-slate-500 transition hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                >
                  {showPassword ? (
                    <EyeOff size={18} />
                  ) : (
                    <Eye size={18} />
                  )}
                </button>
              </div>
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300"
              >
                {error}
              </div>
            )}

            {verificationNotice && (
              <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                {verificationNotice === "needed" ? (
                  <>
                    <p>Your email address must be confirmed before you can sign in.</p>
                    <button type="button" onClick={resendVerification} disabled={!email || resendingVerification} className="font-semibold underline disabled:opacity-50">
                      {resendingVerification ? "Sending a verification link…" : "Send a new verification link"}
                    </button>
                  </>
                ) : verificationNotice}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-lg text-base font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              style={{ backgroundColor: "var(--linda-navy)" }}
            >
              {loading && (
                <Loader2 size={18} className="animate-spin" />
              )}
              {loading ? "Signing in" : "Sign in"}
            </button>

            {registrationOpen && (
              <p className="text-center text-sm text-slate-600 dark:text-slate-400">
                New to LINDA?{" "}
                <Link
                  href="/register"
                  className="font-semibold text-slate-900 underline underline-offset-4 dark:text-white"
                >
                  Create your business account
                </Link>
              </p>
            )}

            <p className="text-center text-sm">
              <Link
                href="/pricing"
                className="text-slate-600 underline underline-offset-4 dark:text-slate-400"
              >
                See pricing
              </Link>
            </p>

            <p className="flex items-center justify-center gap-1.5 pt-2 text-xs text-slate-500 dark:text-slate-400">
              <Lock size={12} aria-hidden="true" />
              Your workspace is private to your business.
            </p>
          </form>
          </div>
        </div>

        <footer className="mt-10 text-center text-xs text-slate-500 dark:text-slate-400">
          <p className="font-medium text-slate-600 dark:text-slate-300">
            LINDA | {PLATFORM_SLOGAN}
          </p>
          <p className="mt-0.5">Powered by {PLATFORM_OWNER}.</p>
        </footer>
      </section>
    </main>
  );
}
