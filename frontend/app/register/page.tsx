"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Briefcase, HeartHandshake, Loader2 } from "lucide-react";

import api from "@/lib/api";
import { saveToken } from "@/lib/auth";
import { getApiErrorMessage } from "@/lib/format";

type Kind = "funeral" | "general";

const KINDS: { value: Kind; title: string; body: string; icon: typeof Briefcase }[] = [
  {
    value: "funeral",
    title: "A funeral business",
    body: "Cases, mortuary, memberships, families, transport, quotes and invoices — the whole funeral platform.",
    icon: HeartHandshake,
  },
  {
    value: "general",
    title: "Another kind of business",
    body: "Manage your team and tasks, record money in and out and see profit or loss. KAI gives work to the right person.",
    icon: Briefcase,
  },
];

export default function RegisterPage() {
  const router = useRouter();
  const [open, setOpen] = useState<boolean | null>(null);
  const [kind, setKind] = useState<Kind>("funeral");
  const [businessName, setBusinessName] = useState("");
  const [phone, setPhone] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get<{ open: boolean }>("/auth/registration-status")
      .then((r) => setOpen(r.data.open))
      .catch(() => setOpen(true));
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError("The two passwords are not the same.");
      return;
    }
    try {
      setBusy(true);
      setError("");
      const r = await api.post("/auth/register", {
        business_name: businessName,
        business_phone: phone.trim() || null,
        business_type: kind,
        full_name: fullName,
        email,
        password,
      });
      saveToken(r.data.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(getApiErrorMessage(err, "We could not create your account."));
      setBusy(false);
    }
  }

  const input =
    "w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-200";

  return (
    <main className="mx-auto max-w-xl space-y-6 p-4 py-10 sm:p-8">
      <header>
        <h1 className="text-3xl font-bold text-slate-900">Create your account</h1>
        <p className="mt-1 text-sm text-slate-600">
          Already registered?{" "}
          <Link href="/login" className="font-medium text-slate-900 underline">
            Sign in
          </Link>
        </p>
      </header>

      {open === false ? (
        <p className="rounded-xl border bg-amber-50 p-4 text-sm text-amber-900">
          Sign-up is closed. Ask your administrator to create your account.
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          <fieldset>
            <legend className="mb-2 text-sm font-semibold text-slate-900">What kind of business is it?</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              {KINDS.map(({ value, title, body, icon: Icon }) => (
                <label
                  key={value}
                  className={`cursor-pointer rounded-xl border p-4 text-sm ${kind === value ? "border-slate-900 bg-slate-50 ring-2 ring-slate-900" : "hover:bg-slate-50"}`}
                >
                  <input type="radio" name="kind" value={value} checked={kind === value} onChange={() => setKind(value)} className="sr-only" />
                  <Icon size={22} className="mb-2 text-slate-800" />
                  <span className="block font-semibold text-slate-900">{title}</span>
                  <span className="mt-1 block text-xs text-slate-600">{body}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {error && (
            <p role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </p>
          )}

          <label className="block text-sm font-medium text-slate-800">
            Business name
            <input className={`${input} mt-1`} value={businessName} onChange={(e) => setBusinessName(e.target.value)} required minLength={2} maxLength={150} />
          </label>
          <label className="block text-sm font-medium text-slate-800">
            Business phone (optional)
            <input className={`${input} mt-1`} value={phone} onChange={(e) => setPhone(e.target.value)} maxLength={30} inputMode="tel" />
          </label>
          <label className="block text-sm font-medium text-slate-800">
            Your full name
            <input className={`${input} mt-1`} value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={2} maxLength={150} autoComplete="name" />
          </label>
          <label className="block text-sm font-medium text-slate-800">
            Your email
            <input className={`${input} mt-1`} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-medium text-slate-800">
              Password (8 or more characters)
              <input className={`${input} mt-1`} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} maxLength={128} autoComplete="new-password" />
            </label>
            <label className="block text-sm font-medium text-slate-800">
              Repeat the password
              <input className={`${input} mt-1`} type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} autoComplete="new-password" />
            </label>
          </div>

          <button
            type="submit"
            disabled={busy || open === null}
            className="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-slate-900 text-base font-semibold text-white disabled:opacity-60"
          >
            {busy && <Loader2 size={18} className="animate-spin" />}
            {busy ? "Creating your account" : "Create account"}
          </button>
          <p className="text-xs text-slate-500">You will be the main administrator and can invite your team afterwards.</p>
        </form>
      )}
    </main>
  );
}
