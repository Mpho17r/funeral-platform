"use client";

import {
  FormEvent,
  useState,
} from "react";

import { useRouter } from "next/navigation";

import {
  Eye,
  EyeOff,
  Loader2,
} from "lucide-react";

import api from "@/lib/api";
import { saveToken } from "@/lib/auth";
import { useBranding } from "@/components/BrandingProvider";

export default function LoginPage() {
  const router = useRouter();

  const { branding, logoObjectUrl } = useBranding();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const primary = branding?.primary_color || "#162620";
  const accent = branding?.secondary_color || "#5e8077";
  const businessName = branding?.name || "FuneralOS";

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
      <aside
        className="relative hidden overflow-hidden text-white lg:flex lg:flex-col lg:justify-between lg:p-14"
        style={{ backgroundColor: primary }}
      >
        {/* Quiet ripples: a single decorative motif, nothing else competes */}
        <svg
          aria-hidden="true"
          viewBox="0 0 600 600"
          className="pointer-events-none absolute -bottom-40 -right-40 h-[640px] w-[640px] text-white"
          fill="none"
          stroke="currentColor"
        >
          {[60, 110, 160, 210, 260, 310].map((radius, index) => (
            <circle
              key={radius}
              cx="300"
              cy="300"
              r={radius}
              strokeWidth="1"
              opacity={0.22 - index * 0.03}
            />
          ))}
        </svg>

        <div className="relative flex items-center gap-3">
          {logoObjectUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={logoObjectUrl}
              alt=""
              className="h-11 w-11 rounded-xl bg-white object-contain p-1"
            />
          ) : (
            <span
              className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10 font-display text-2xl ring-1 ring-white/25"
            >
              {businessName.charAt(0).toUpperCase()}
            </span>
          )}

          <span className="text-lg font-semibold">
            {businessName}
          </span>
        </div>

        <div className="relative max-w-md">
          <h1 className="font-display text-5xl leading-[1.08]">
            Every arrangement, handled with care.
          </h1>

          <p className="mt-6 max-w-sm text-base leading-relaxed text-white/75">
            Cases, families, memberships and payments in one place, so
            your team can give each family their full attention.
          </p>
        </div>

        <div
          aria-hidden="true"
          className="relative h-1 w-24 rounded-full"
          style={{ backgroundColor: accent }}
        />
      </aside>

      {/* FORM */}
      <section className="flex items-center justify-center px-6 py-12 sm:px-10">
        <div className="w-full max-w-sm">
          {/* Brand, shown when the side panel is hidden */}
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <span
              className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-xl font-display text-2xl text-white"
              style={{ backgroundColor: primary }}
            >
              {logoObjectUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={logoObjectUrl}
                  alt=""
                  className="h-full w-full bg-white object-contain p-1"
                />
              ) : (
                businessName.charAt(0).toUpperCase()
              )}
            </span>

            <span className="text-lg font-semibold text-slate-900 dark:text-white">
              {businessName}
            </span>
          </div>

          <h2 className="font-display text-4xl text-slate-900 dark:text-white">
            Sign in
          </h2>

          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Use the email and password your administrator gave you.
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
          </form>
        </div>
      </section>
    </main>
  );
}
