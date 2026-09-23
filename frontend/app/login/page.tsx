"use client";

import {
  FormEvent,
  useState,
} from "react";

import { useRouter } from "next/navigation";

import {
  Eye,
  EyeOff,
  Lock,
  Mail,
} from "lucide-react";

import api from "@/lib/api";
import { saveToken } from "@/lib/auth";
import { useBranding } from "@/components/BrandingProvider";

export default function LoginPage() {
  const router = useRouter();

  const {
    branding,
  } = useBranding();

  const [email, setEmail] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [showPassword, setShowPassword] =
    useState(false);

  const [error, setError] =
    useState("");

  const [loading, setLoading] =
    useState(false);

  const primary =
    branding?.primary_color ||
    "#0f172a";

  const secondary =
    branding?.secondary_color ||
    "#64748b";

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      const response =
        await api.post(
          "/auth/login",
          {
            email,
            password,
          },
        );

      saveToken(
        response.data.access_token,
      );

      router.push("/dashboard");
    } catch (error: any) {
      if (
        error.response?.data?.detail
      ) {
        setError(
          error.response.data.detail,
        );
      } else {
        setError(
          "Unable to connect to FuneralOS.",
        );
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      className="
        flex min-h-screen items-center
        justify-center px-6
        bg-slate-100
        dark:bg-slate-950
        transition-colors duration-200
      "
    >
      <div className="w-full max-w-md">
        <div
          className="
            overflow-hidden rounded-3xl
            border border-slate-200
            bg-white shadow-xl
            dark:border-slate-800
            dark:bg-slate-900
          "
        >
          {/* BRAND HEADER */}
          <div
            className="h-2"
            style={{
              background: `linear-gradient(
                90deg,
                ${primary},
                ${secondary}
              )`,
            }}
          />

          <div className="p-8">
            <div className="mb-8 text-center">
              <div
                className="
                  mx-auto mb-4 flex h-14 w-14
                  items-center justify-center
                  overflow-hidden rounded-2xl
                  text-white shadow-sm
                "
                style={{
                  backgroundColor:
                    primary,
                }}
              >
                <span className="text-xl font-bold">
                  {branding?.name
                    ?.charAt(0)
                    .toUpperCase() || "F"}
                </span>
              </div>

              <h1
                className="
                  text-2xl font-bold
                  text-slate-900
                  dark:text-white
                "
              >
                {branding?.name ||
                  "FuneralOS"}
              </h1>

              <p
                className="
                  mt-2 text-sm
                  text-slate-500
                  dark:text-slate-400
                "
              >
                Funeral management platform
              </p>
            </div>

            <form
              onSubmit={handleSubmit}
              className="space-y-5"
            >
              {/* EMAIL */}
              <div>
                <label
                  htmlFor="email"
                  className="
                    mb-2 block text-sm
                    font-medium
                    text-slate-700
                    dark:text-slate-300
                  "
                >
                  Email address
                </label>

                <div className="relative">
                  <Mail
                    size={18}
                    className="
                      absolute left-3
                      top-1/2
                      -translate-y-1/2
                      text-slate-400
                    "
                  />

                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(event) =>
                      setEmail(
                        event.target.value,
                      )
                    }
                    placeholder="admin@example.com"
                    required
                    className="
                      w-full rounded-xl
                      border border-slate-300
                      bg-white py-3 pl-10 pr-4
                      text-sm text-slate-900
                      outline-none transition
                      focus:ring-2
                      dark:border-slate-700
                      dark:bg-slate-800
                      dark:text-white
                    "
                    style={{
                      borderColor:
                        undefined,
                    }}
                  />
                </div>
              </div>

              {/* PASSWORD */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label
                    htmlFor="password"
                    className="
                      block text-sm
                      font-medium
                      text-slate-700
                      dark:text-slate-300
                    "
                  >
                    Password
                  </label>

                  <button
                    type="button"
                    onClick={() =>
                      router.push(
                        "/forgot-password",
                      )
                    }
                    className="
                      text-xs font-medium
                      transition hover:underline
                    "
                    style={{
                      color: secondary,
                    }}
                  >
                    Forgot password?
                  </button>
                </div>

                <div className="relative">
                  <Lock
                    size={18}
                    className="
                      absolute left-3
                      top-1/2
                      -translate-y-1/2
                      text-slate-400
                    "
                  />

                  <input
                    id="password"
                    type={
                      showPassword
                        ? "text"
                        : "password"
                    }
                    value={password}
                    onChange={(event) =>
                      setPassword(
                        event.target.value,
                      )
                    }
                    placeholder="••••••••"
                    required
                    className="
                      w-full rounded-xl
                      border border-slate-300
                      bg-white py-3 pl-10 pr-12
                      text-sm text-slate-900
                      outline-none transition
                      focus:ring-2
                      dark:border-slate-700
                      dark:bg-slate-800
                      dark:text-white
                    "
                  />

                  <button
                    type="button"
                    aria-label={
                      showPassword
                        ? "Hide password"
                        : "Show password"
                    }
                    onClick={() =>
                      setShowPassword(
                        (current) =>
                          !current,
                      )
                    }
                    className="
                      absolute right-3
                      top-1/2
                      -translate-y-1/2
                      rounded-md p-1
                      text-slate-400
                      transition
                      hover:text-slate-700
                      dark:hover:text-white
                    "
                  >
                    {showPassword ? (
                      <EyeOff size={18} />
                    ) : (
                      <Eye size={18} />
                    )}
                  </button>
                </div>
              </div>

              {/* ERROR */}
              {error && (
                <div
                  className="
                    rounded-xl border
                    border-red-200
                    bg-red-50 px-4 py-3
                    text-sm text-red-700
                    dark:border-red-900
                    dark:bg-red-950
                    dark:text-red-300
                  "
                >
                  {error}
                </div>
              )}

              {/* LOGIN */}
              <button
                type="submit"
                disabled={loading}
                className="
                  w-full rounded-xl py-3
                  text-sm font-semibold
                  text-white shadow-sm
                  transition
                  hover:opacity-90
                  disabled:cursor-not-allowed
                  disabled:opacity-60
                "
                style={{
                  backgroundColor: primary,
                }}
              >
                {loading
                  ? "Signing in..."
                  : "Sign in"}
              </button>
            </form>

            <div className="mt-8 text-center">
              <p
                className="
                  text-xs
                  text-slate-400
                  dark:text-slate-500
                "
              >
                Secure access to your
                funeral management system.
              </p>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}