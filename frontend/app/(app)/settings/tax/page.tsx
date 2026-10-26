"use client";

import { ArrowLeft, ReceiptText } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { useCurrentUser } from "@/components/CurrentUserProvider";
import { Field, inputClass } from "@/components/Dialog";
import { Banner, ErrorNote } from "@/components/Notices";
import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";

type TaxSettings = {
  vat_registered: boolean;
  vat_registration_number: string | null;
  prices_include_vat: boolean;
  standard_vat_rate: string;
  currency: string;
};

export default function BusinessTaxSettingsPage() {
  const router = useRouter();
  const { user } = useCurrentUser();
  const businessId = user?.business_id;
  const [form, setForm] = useState({
    vat_registered: false,
    vat_registration_number: "",
    prices_include_vat: false,
  });
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!businessId) return;
    api.get<TaxSettings>(`/businesses/${businessId}/tax-settings`)
      .then(({ data }) => {
        setForm({
          vat_registered: data.vat_registered,
          vat_registration_number: data.vat_registration_number ?? "",
          prices_include_vat: data.prices_include_vat,
        });
        setLoaded(true);
      })
      .catch((err) => setError(getApiErrorMessage(err, "Could not load tax settings.")));
  }, [businessId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      await api.patch(`/businesses/${businessId}/tax-settings`, {
        ...form,
        vat_registration_number: form.vat_registered ? form.vat_registration_number.trim() : null,
      });
      setSaved(true);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save tax settings."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen bg-[var(--fos-page)] text-[var(--fos-text)]">
      <section className="mx-auto max-w-2xl p-6 md:p-8">
        <button type="button" onClick={() => router.push("/settings")} className="mb-4 flex items-center gap-2 text-sm font-medium text-[var(--fos-text-muted)] transition hover:text-[var(--fos-text)]">
          <ArrowLeft size={16} /> Back to Settings
        </button>
        <div className="flex items-center gap-3">
          <ReceiptText size={25} />
          <h1 className="text-2xl font-bold">Business & Tax</h1>
        </div>
        <p className="mt-2 text-sm leading-6 text-[var(--fos-text-muted)]">
          Set your business VAT registration details. FuneralOS controls the standard VAT rate centrally; this page does not let users choose their own rate.
        </p>
        {saved && <div className="mt-6"><Banner tone="success" onDismiss={() => setSaved(false)}>Tax settings were saved.</Banner></div>}
        {error && <div className="mt-6"><ErrorNote message={error} /></div>}
        <form onSubmit={submit} className="mt-6 space-y-5 rounded-2xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6">
          <div className="rounded-xl border border-[var(--fos-border)] p-4">
            <p className="text-sm font-semibold">South African standard VAT rate</p>
            <p className="mt-1 text-2xl font-bold">15%</p>
            <p className="mt-1 text-sm text-[var(--fos-text-muted)]">Controlled by FuneralOS and applied only where the business and supply are eligible.</p>
          </div>
          <label className="flex items-start gap-3 text-sm">
            <input type="checkbox" checked={form.vat_registered} onChange={(e) => { setSaved(false); setForm((f) => ({ ...f, vat_registered: e.target.checked, vat_registration_number: e.target.checked ? f.vat_registration_number : "" })); }} disabled={!loaded} className="mt-1" />
            <span><strong>My business is VAT registered</strong><span className="mt-1 block text-[var(--fos-text-muted)]">Only enable this if your business is registered with SARS.</span></span>
          </label>
          {form.vat_registered && <Field label="VAT registration number"><input className={inputClass} value={form.vat_registration_number} onChange={(e) => { setSaved(false); setForm((f) => ({ ...f, vat_registration_number: e.target.value })); }} required maxLength={50} disabled={!loaded} /></Field>}
          <div className="rounded-xl border border-[var(--fos-border)] p-4">
            <p className="text-sm font-semibold">How are your prices entered?</p>
            <p className="mt-1 text-sm text-[var(--fos-text-muted)]">Choose the convention your team normally uses for new quotes and invoices.</p>
            <div className="mt-3 space-y-3">
              <label className="flex items-center gap-3 text-sm"><input type="radio" name="pricing" checked={!form.prices_include_vat} onChange={() => { setSaved(false); setForm((f) => ({ ...f, prices_include_vat: false })); }} disabled={!loaded} /> Prices exclude VAT (VAT is added to eligible items)</label>
              <label className="flex items-center gap-3 text-sm"><input type="radio" name="pricing" checked={form.prices_include_vat} onChange={() => { setSaved(false); setForm((f) => ({ ...f, prices_include_vat: true })); }} disabled={!loaded} /> Prices include VAT (VAT is extracted from eligible items)</label>
            </div>
          </div>
          <p className="text-xs leading-5 text-[var(--fos-text-muted)]">Saving these settings records your business preferences. Existing invoices will not be recalculated by changing these settings.</p>
          <button type="submit" disabled={saving || !loaded} className="rounded-xl bg-[var(--fos-primary)] px-5 py-2.5 text-sm font-semibold text-[var(--fos-on-primary)] transition hover:bg-[var(--fos-primary-hover)] disabled:opacity-50">{saving ? "Saving…" : "Save tax settings"}</button>
        </form>
      </section>
    </main>
  );
}
