"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import api from "@/lib/api";

export type Branch = {
  id: string;
  business_id: string;
  name: string;
  code: string;
  phone: string | null;
  email: string | null;
  address: string | null;
  notes: string | null;
  is_main: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BranchSummary = {
  branch_id: string;
  active_staff: number;
  active_resources: number;
  members: number;
  live_cases: number;
  total_cases: number;
};

/**
 * The business's branches, for filters, forms and badges.
 *
 * Branch screens are an extra. If the user may not list branches the
 * hook returns an empty list, and every branch control hides itself.
 */
export function useBranches() {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loaded, setLoaded] = useState(false);

  const reload = useCallback(async () => {
    try {
      const response = await api.get<Branch[]>("/branches", {
        params: { include_inactive: true },
      });

      setBranches(response.data);
    } catch {
      setBranches([]);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    // The fetch is async, so state is only set after the response.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void reload();
  }, [reload]);

  const byId = useMemo(
    () => new Map(branches.map((branch) => [branch.id, branch])),
    [branches]
  );

  const active = useMemo(
    () => branches.filter((branch) => branch.is_active),
    [branches]
  );

  return {
    branches,
    active,
    byId,
    loaded,
    // With one branch there is nothing to choose or filter by.
    multiple: active.length > 1,
    reload,
  };
}
