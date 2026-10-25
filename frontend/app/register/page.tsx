"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import api from "@/lib/api";
import { saveToken } from "@/lib/auth";

type RegistrationStatus = {
  open: boolean;
};

type ApiError = {
  response?: {
    data?: {
      detail?: unknown;
    };
  };
};

export default function RegisterPage() {
  const router = useRouter();

  const [status, setStatus] = useState<"checking" | "open" | "closed" | "error">("checking");
  const [businessName, setBusinessName] = useState("");
  const [businessPhone, setBusinessPhone] = useState("");
  const [businessEmail, setBusinessEmail] = useState("");
  const [businessAddress, setBusinessAddress] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;

    api.get<RegistrationStatus>("/auth/registration-status")
      .then((response) => {
        if (active) setStatus(response.data.open ? "open" : "closed");
      })
      .catch(() => {
        if (active) setStatus("error");
      });

    return () => {
      active = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }

    if (password.length < 12) {
      setError("Please use a password with at least 12 characters.");
      return;
    }

    setLoading(true);
    try {
      const response = await api.post("/auth/register", {
        business_name: businessName.trim(),
        business_phone: businessPhone.trim() || null,
        business_email: businessEmail.trim() || null,
        business_address: businessAddress.trim() || null,
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password,
      });

      saveToken(response.data.access_token);
      router.replace("/dashboard");
    } catch (err) {
      const detail = (err as ApiError).response?.data?.detail;
      setError(
        typeof detail === "string" && detail
          ? detail
          : "We couldn't create your account. Check your connection and try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  const fieldClass = "mt-1.5 h-11 w-full rounded-lg border border-slate-300 bg-white px-3.5 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:ring-slate-800";
  const labelClass = "block text-sm font-medium text-slate-700 dark:text-slate-300";

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-10 dark:bg-slate-950 sm:px-6">
      <div className="mx-auto max-w-2xl">
        <header className="mb-8 text-center">
          <Link href="/login" className="text-sm font-semibold tracking-wide text-slate-500 hover:text-slate-900 dark:hover:text-white">
            FUNERALOS
          </Link>
          <h1 className="mt-4 font-display text-3xl text-slate-900 dark:text-white sm:text-4xl">
            Create your funeral business account
          </h1>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-600 dark:text-slate-400">
            Set up your business workspace. Your account starts with a 30-day trial, and you’ll become its Main Admin.
          </p>
        </header>

        {status === "checking" && (
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
            Checking registration availability…
          </div>
        )}

        {status === "error" && (
          <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            We couldn’t check whether registration is available. Please refresh the page or try again shortly.
          </div>
        )}

        {status === "closed" && (
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-center dark:border-slate-800 dark:bg-slate-900">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Registration is currently closed</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-400">
              Please contact the platform administrator for access.
            </p>
            <Link href="/login" className="mt-5 inline-flex h-11 items-center justify-center rounded-lg bg-slate-900 px-5 text-sm font-semibold text-white hover:opacity-90 dark:bg-white dark:text-slate-900">
              Go to sign in
            </Link>
          </div>
        )}

        {status === "open" && (
          <form onSubmit={handleSubmit} className="space-y-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-8">
            <section>
              <h2 className="text-base font-semibold text-slate-900 dark:text-white">Your business</h2>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <label htmlFor="businessName" className={labelClass}>Business name *</label>
                  <input id="businessName" name="business_name" autoComplete="organization" value={businessName} onChange={(e) => setBusinessName(e.target.value)} minLength={2} maxLength={150} required className={fieldClass} />
                </div>
                <div>
                  <label htmlFor="businessPhone" className={labelClass}>Business phone</label>
                  <input id="businessPhone" name="business_phone" type="tel" autoComplete="tel" value={businessPhone} onChange={(e) => setBusinessPhone(e.target.value)} maxLength={30} className={fieldClass} />
                </div>
                <div>
                  <label htmlFor="businessEmail" className={labelClass}>Business email</label>
                  <input id="businessEmail" name="business_email" type="email" autoComplete="email" value={businessEmail} onChange={(e) => setBusinessEmail(e.target.value)} className={fieldClass} />
                </div>
                <div className="sm:col-span-2">
                  <label htmlFor="businessAddress" className={labelClass}>Business address</label>
                  <textarea id="businessAddress" name="business_address" autoComplete="street-address" value={businessAddress} onChange={(e) => setBusinessAddress(e.target.value)} rows={2} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3.5 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:ring-slate-800" />
                </div>
              </div>
            </section>

            <section className="border-t border-slate-200 pt-6 dark:border-slate-800">
              <h2 className="text-base font-semibold text-slate-900 dark:text-white">Your administrator account</h2>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <label htmlFor="fullName" className={labelClass}>Your full name *</label>
                  <input id="fullName" name="full_name" autoComplete="name" value={fullName} onChange={(e) => setFullName(e.target.value)} minLength={2} maxLength={150} required className={fieldClass} />
                </div>
                <div className="sm:col-span-2">
                  <label htmlFor="email" className={labelClass}>Sign-in email *</label>
                  <input id="email" name="email" type="email" autoComplete="username" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} required className={fieldClass} />
                </div>
                <div>
                  <label htmlFor="password" className={labelClass}>Password *</label>
                  <input id="password" name="password" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={12} maxLength={128} required className={fieldClass} aria-describedby="password-help" />
                  <p id="password-help" className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">Use at least 12 characters.</p>
                </div>
                <div>
                  <label htmlFor="confirmPassword" className={labelClass}>Confirm password *</label>
                  <input id="confirmPassword" name="confirm_password" type="password" autoComplete="new-password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} minLength={12} maxLength={128} required className={fieldClass} />
                </div>
              </div>
            </section>

            {error && (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300">
                {error}
              </div>
            )}

            <div className="rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-600 dark:bg-slate-950 dark:text-slate-400">
              By creating an account, you confirm that you are authorised to register this business and agree to use the service lawfully. Subscription payment setup can be completed separately during the trial.
            </div>

            <button type="submit" disabled={loading} className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-900">
              {loading && <Loader2 size={18} className="animate-spin" />}
              {loading ? "Creating your account…" : "Create account and start trial"}
            </button>
            <p className="text-center text-sm text-slate-600 dark:text-slate-400">
              Already have an account? <Link href="/login" className="font-semibold text-slate-900 underline underline-offset-4 dark:text-white">Sign in</Link>
            </p>
          </form>
        )}
      </div>
    </main>
  );
}
