"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { useBranding } from "@/components/BrandingProvider";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Field, inputClass } from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";
import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";

type Business = {
  name: string;
  phone: string | null;
  email: string | null;
  address: string | null;
};

export default function BusinessDetailsPage() {
  const router = useRouter();
  const { user } = useCurrentUser();
  const { refreshBranding } = useBranding();

  const [form, setForm] = useState({
    name: "",
    phone: "",
    email: "",
    address: "",
  });
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const businessId = user?.business_id;

  useEffect(() => {
    if (!businessId) {
      return;
    }

    api
      .get<Business>(`/businesses/${businessId}`)
      .then((response) => {
        const b = response.data;

        setForm({
          name: b.name ?? "",
          phone: b.phone ?? "",
          email: b.email ?? "",
          address: b.address ?? "",
        });
        setLoaded(true);
      })
      .catch((err) =>
        setError(getApiErrorMessage(err, "Could not load your details.")),
      );
  }, [businessId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSaved(false);

    try {
      await api.patch(`/businesses/${businessId}/contact`, form);
      await refreshBranding();
      setSaved(true);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save your details."));
    } finally {
      setSaving(false);
    }
  }

  const set = (key: keyof typeof form) => (value: string) => {
    setSaved(false);
    setForm((f) => ({ ...f, [key]: value }));
  };

  return (
    <main className="min-h-screen bg-[var(--fos-page)] text-[var(--fos-text)]">
      <section className="mx-auto max-w-2xl p-6 md:p-8">
        <button
          type="button"
          onClick={() => router.push("/settings")}
          className="mb-4 flex items-center gap-2 text-sm font-medium text-[var(--fos-text-muted)] transition hover:text-[var(--fos-text)]"
        >
          <ArrowLeft size={16} />
          Back to Settings
        </button>

        <h1 className="text-2xl font-bold">Business details</h1>
        <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
          Your name and contact details appear in reminders and messages to
          families.
        </p>

        {saved && (
          <div className="mt-6">
            <Banner tone="success" onDismiss={() => setSaved(false)}>
              Your details were saved.
            </Banner>
          </div>
        )}

        {error && (
          <div className="mt-6">
            <ErrorNote message={error} />
          </div>
        )}

        <form
          onSubmit={submit}
          className="mt-6 space-y-4 rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6"
        >
          <Field label="Business name">
            <input
              className={inputClass}
              value={form.name}
              onChange={(e) => set("name")(e.target.value)}
              required
              maxLength={255}
              disabled={!loaded}
            />
          </Field>

          <Field label="Phone number">
            <input
              className={inputClass}
              value={form.phone}
              onChange={(e) => set("phone")(e.target.value)}
              maxLength={50}
              inputMode="tel"
              disabled={!loaded}
            />
          </Field>

          <Field label="Email address">
            <input
              className={inputClass}
              type="email"
              value={form.email}
              onChange={(e) => set("email")(e.target.value)}
              maxLength={255}
              disabled={!loaded}
            />
          </Field>

          <Field label="Address">
            <textarea
              className={inputClass}
              rows={3}
              value={form.address}
              onChange={(e) => set("address")(e.target.value)}
              maxLength={1000}
              disabled={!loaded}
            />
          </Field>

          <button
            type="submit"
            disabled={saving || !loaded}
            className="rounded-xl bg-[var(--fos-primary)] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[var(--fos-primary-hover)] disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save details"}
          </button>
        </form>
      </section>
    </main>
  );
}
