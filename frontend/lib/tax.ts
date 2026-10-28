"use client";

import { useEffect, useState } from "react";

import api from "@/lib/api";
import { useCurrentUser } from "@/components/CurrentUserProvider";

export type TaxSettings = {
  enabled: boolean;
  name: string;
  rate: number;
};

const OFF: TaxSettings = { enabled: false, name: "VAT", rate: 0 };

/** The business's tax setting (VAT). When enabled the server works the
 * tax out itself, so screens show it instead of asking for it. */
export function useTax(): TaxSettings {
  const { user } = useCurrentUser();
  const businessId = user?.business_id;
  const [tax, setTax] = useState<TaxSettings>(OFF);

  useEffect(() => {
    if (!businessId) return;
    api
      .get<{ tax_enabled: boolean; tax_name: string; tax_rate: number }>(
        `/businesses/${businessId}`,
      )
      .then((r) =>
        setTax({
          enabled: r.data.tax_enabled,
          name: r.data.tax_name,
          rate: Number(r.data.tax_rate),
        }),
      )
      .catch(() => setTax(OFF));
  }, [businessId]);

  return tax;
}
