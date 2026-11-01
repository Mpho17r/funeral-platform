"use client";

import { Suspense } from "react";
import { ArrowLeft } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";

import api from "@/lib/api";
import SalesDocumentForm, { type DocumentFormValues } from "@/components/SalesDocumentForm";
import type { SalesDoc } from "@/lib/sales";

function NewDocument() {
  const router = useRouter();
  const customer = useSearchParams().get("customer") ?? "";

  async function create(values: DocumentFormValues) {
    const r = await api.post<SalesDoc>("/sales/documents", values);
    router.push(`/sales/${r.data.id}`);
  }

  return (
    <main className="mx-auto max-w-3xl space-y-5 p-4 sm:p-6">
      <button
        type="button"
        onClick={() => router.push("/sales")}
        className="flex items-center gap-1 text-sm text-slate-600 hover:underline"
      >
        <ArrowLeft size={16} /> Quotes &amp; invoices
      </button>
      <h1 className="text-2xl font-bold">New quote or invoice</h1>
      <div className="rounded-2xl border bg-white p-5">
        <SalesDocumentForm
          initial={{
            customer_id: customer,
            document_type: "invoice",
            lines: [],
            discount: 0,
            due_date: null,
            valid_until: null,
            notes: null,
          }}
          submitLabel="Save as draft"
          onSubmit={create}
          onCancel={() => router.push("/sales")}
        />
      </div>
    </main>
  );
}

export default function NewDocumentPage() {
  return (
    <Suspense fallback={null}>
      <NewDocument />
    </Suspense>
  );
}
