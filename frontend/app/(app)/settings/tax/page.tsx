"use client";

import { FormEvent, useEffect, useState } from "react";
import { ArrowLeft, Loader2, Percent, Save } from "lucide-react";
import { useRouter } from "next/navigation";

import api from "@/lib/api";
import { getApiErrorMessage } from "@/lib/format";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { ErrorNote } from "@/components/Notices";

const PRESETS = [
  { country: "South Africa", name: "VAT", rate: 15 },
  { country: "Botswana", name: "VAT", rate: 14 },
  { country: "Namibia", name: "VAT", rate: 15 },
  { country: "Zimbabwe", name: "VAT", rate: 15 },
  { country: "Zambia", name: "VAT", rate: 16 },
  { country: "Kenya", name: "VAT", rate: 16 },
  { country: "Nigeria", name: "VAT", rate: 7.5 },
];

export default function TaxSettingsPage() {
  const router = useRouter();
  const { user } = useCurrentUser();
  const businessId = user?.business_id;
  const isMainAdmin = user?.role === "main_admin";

  const [enabled, setEnabled] = useState(true);
  const [name, setName] = useState("VAT");
  const [rate, setRate] = useState("15");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!businessId) return;
    api
      .get(`/businesses/${businessId}`)
      .then((r) => {
        setEnabled(Boolean(r.data.tax_enabled));
        setName(r.data.tax_name ?? "VAT");
        setRate(String(r.data.tax_rate ?? 15));
      })
      .catch((err) => setError(getApiErrorMessage(err, "Could not load tax settings.")))
      .finally(() => setLoading(false));
  }, [businessId]);

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      setSaving(true);
      setError("");
      setMessage("");
      await api.patch(`/businesses/${businessId}/tax`, {
        tax_enabled: enabled,
        tax_name: name.trim() || "VAT",
        tax_rate: Number(rate),
      });
      setMessage("Saved. New quotes and invoices use this. Issued ones do not change.");
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save."));
    } finally {
      setSaving(false);
    }
  }

  const example = Number.isFinite(Number(rate))
    ? (1000 * Number(rate)) / 100
    : 0;

  return (
    <main className="mx-auto max-w-2xl space-y-5 p-4 sm:p-6">
      <button
        type="button"
        onClick={() => router.push("/settings")}
        className="flex items-center gap-1 text-sm text-slate-600 hover:underline"
      >
        <ArrowLeft size={16} /> Settings
      </button>

      <header className="flex items-center gap-3">
        <div className="rounded-xl bg-slate-900 p-3 text-white">
          <Percent size={20} />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Tax (VAT)</h1>
          <p className="text-sm text-slate-500">
            Set the tax for your country. It is added to quotes and invoices
            automatically.
          </p>
        </div>
      </header>

      {error && <ErrorNote message={error} />}
      {!isMainAdmin && !loading && (
        <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          Only the main administrator can change the tax.
        </p>
      )}

      {loading ? (
        <Loader2 className="animate-spin" />
      ) : (
        <form onSubmit={save} className="space-y-5 rounded-2xl border bg-white p-5">
          <label className="flex items-center gap-3 text-sm font-medium">
            <input
              type="checkbox"
              checked={enabled}
              disabled={!isMainAdmin}
              onChange={(e) => setEnabled(e.target.checked)}
              className="h-4 w-4"
            />
            Charge tax on quotes and invoices
          </label>

          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">Quick pick by country</p>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((p) => (
                <button
                  key={p.country}
                  type="button"
                  disabled={!isMainAdmin}
                  onClick={() => {
                    setName(p.name);
                    setRate(String(p.rate));
                    setEnabled(true);
                  }}
                  className="rounded-full border px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
                >
                  {p.country} {p.rate}%
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Check the current rate with your tax authority. You can type any rate.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">Tax name</span>
              <input
                value={name}
                maxLength={20}
                disabled={!isMainAdmin}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-lg border px-3 py-2"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">Rate (%)</span>
              <input
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={rate}
                disabled={!isMainAdmin}
                onChange={(e) => setRate(e.target.value)}
                className="w-full rounded-lg border px-3 py-2"
              />
            </label>
          </div>

          <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
            Prices are entered without tax. Example: R1 000.00 + {name} {rate}% =
            R{example.toFixed(2)} tax, total R{(1000 + example).toFixed(2)}.
          </p>

          {isMainAdmin && (
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-60"
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              Save
            </button>
          )}
        </form>
      )}
    </main>
  );
}
