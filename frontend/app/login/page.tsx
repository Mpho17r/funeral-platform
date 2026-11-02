"use client";

import {
  FormEvent,
  useEffect,
  useState,
} from "react";
import Link from "next/link";

import { useRouter } from "next/navigation";

import {
  Eye,
  EyeOff,
  Loader2,
} from "lucide-react";

import api from "@/lib/api";
import { saveToken } from "@/lib/auth";
import LindaLogo from "@/components/LindaLogo";

const HIGHLIGHTS = [
  "Business Management",
  "People and Customers",
  "Finance and Performance",
  "Operations and Workflows",
  "Intelligent Assistance",
];

const MESSAGES = [
  "One business. One connected workspace.",
  "Clarity in every operation.",
  "Better decisions start with better visibility.",
  "Your business operations, working in harmony.",
  "Spend less time managing. More time growing.",
];

export default function LoginPage() {
  const router = useRouter();

  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setMessageIndex((i) => (i + 1) % MESSAGES.length), 5000);
    return () => clearInterval(id);
  }, []);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [registrationOpen, setRegistrationOpen] = useState(false);

  useEffect(() => {
    api
      .get<{ open: boolean }>("/auth/registration-status")
      .then((r) => setRegistrationOpen(r.data.open))
      .catch(() => setRegistrationOpen(false));
  }, []);

  const primary = "#101D2B";

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
    <main className="grid min-h-screen bg-white dark:bg-slate-950 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      {/* BRAND PANEL */}
      <aside className="relative hidden overflow-hidden bg-[#101D2B] text-white lg:flex lg:flex-col lg:justify-between lg:p-14">
        <svg
          aria-hidden="true"
          viewBox="0 0 600 600"
          className="pointer-events-none absolute -bottom-40 -right-40 h-[640px] w-[640px] text-white"
          fill="none"
          stroke="currentColor"
        >
          {[60, 110, 160, 210, 260, 310].map((radius, index) => (
            <circle key={radius} cx="300" cy="300" r={radius} strokeWidth="1" opacity={0.18 - index * 0.025} />
          ))}
        </svg>

        <div className="relative">
          <LindaLogo size={44} tone="light" />
        </div>

        <div className="relative max-w-lg">
          <h1 className="font-display text-5xl leading-[1.08]">
            Run your business. Don&apos;t let your business run you.
          </h1>
          <p className="mt-6 max-w-md text-base leading-relaxed text-white/75">
            From daily operations to long-term growth, LINDA brings your entire business together in one intelligent workspace.
          </p>

          <ul className="mt-8 grid max-w-md gap-3 text-sm text-white/85">
            {HIGHLIGHTS.map((item) => (
              <li key={item} className="flex items-center gap-3">
                <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[#D6A85F]" />
                {item}
              </li>
            ))}
          </ul>

          <p aria-live="polite" className="mt-10 h-5 text-sm font-medium text-[#D6A85F]">
            {MESSAGES[messageIndex]}
          </p>
        </div>

        <p className="relative text-xs text-white/60">
          LINDA | One Platform. Every Business. Powered by Saccharum Technologies.
        </p>
      </aside>

      {/* FORM */}
      <section className="flex flex-col items-center justify-center px-6 py-12 sm:px-10">
        <div className="w-full max-w-sm">
          <div className="mb-10 lg:hidden">
            <LindaLogo size={40} />
          </div>

          <p className="hidden text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 lg:block">
            LINDA
          </p>
          <h2 className="mt-1 font-display text-4xl text-slate-900 dark:text-white">
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

            <button
              type="submit"
              disabled={loading}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-lg text-base font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              style={{ backgroundColor: primary }}
            >
              {loading && (
                <Loader2 size={18} className="animate-spin" />
              )}
              {loading ? "Signing in" : "Sign in"}
            </button>

            {registrationOpen && (
              <p className="text-center text-sm text-slate-600">
                New business?{" "}
                <Link href="/register" className="font-medium underline">
                  Register a business account
                </Link>
              </p>
            )}
          </form>

          <p className="mt-8 text-center text-xs text-slate-500">
            Your connection is encrypted and each business&apos;s data is kept separate.
          </p>
        </div>
      </section>
    </main>
  );
}
