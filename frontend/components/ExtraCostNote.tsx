"use client";

import { useEffect, useState } from "react";

import api from "@/lib/api";
import { Subscription, rands } from "@/lib/pricing";

/** Says what adding one more staff account or branch will add to the bill. */
export function ExtraCostNote({ kind }: { kind: "staff" | "branch" }) {
  const [cents, setCents] = useState(0);
  const [cover, setCover] = useState(0);

  useEffect(() => {
    api
      .get<Subscription>("/subscription")
      .then((r) => {
        setCents(
          kind === "staff"
            ? r.data.next_staff_incl_vat_cents
            : r.data.next_branch_incl_vat_cents,
        );
        setCover(r.data.vat_percent);
      })
      .catch(() => setCents(0));
  }, [kind]);

  if (cents <= 0) return null;

  return (
    <p
      role="note"
      className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
    >
      This {kind === "staff" ? "staff account" : "branch"} is extra and adds{" "}
      <strong>{rands(cents)}</strong> to your monthly bill{cover > 0 ? ` (incl. ${cover}% VAT)` : ""}.
    </p>
  );
}
