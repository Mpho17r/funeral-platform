import type { TaxSettings } from "@/lib/tax";

/** Shown instead of a tax box when the business has tax switched on. */
export function AutoTaxNote({ tax }: { tax: TaxSettings }) {
  return (
    <div className="block">
      <span className="mb-2 block text-sm font-medium text-slate-700">
        {tax.name} ({tax.rate}%)
      </span>
      <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-2.5 text-sm text-slate-600">
        Worked out automatically when you save.
      </p>
    </div>
  );
}
