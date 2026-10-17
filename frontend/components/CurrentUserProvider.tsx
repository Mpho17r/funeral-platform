"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import api from "@/lib/api";

export type CurrentUser = {
  user_id: string;
  business_id: string;
  role: string;
  full_name: string | null;
  email: string | null;
  job_title: string | null;
  branch_id: string | null;
  branch_name: string | null;
};

const ROLE_LABELS: Record<string, string> = {
  main_admin: "Main administrator",
  manager: "Manager",
  staff: "Staff member",
};

/** What the person's access level is called on screen. */
export function roleLabel(role: string | null | undefined): string {
  if (!role) {
    return "";
  }

  return (
    ROLE_LABELS[role] ??
    role.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase())
  );
}

/** "Thandi Nkosi" -> "TN". Falls back to the first letter, then "?". */
export function initialsOf(name: string | null | undefined): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);

  if (parts.length === 0) {
    return "?";
  }

  if (parts.length === 1) {
    return parts[0][0].toUpperCase();
  }

  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/**
 * What to show beneath a person's name: the job they do ("Operations
 * Manager") when one is set, otherwise their access level.
 */
export function titleOf(
  user: Pick<CurrentUser, "job_title" | "role"> | null,
): string {
  if (!user) {
    return "";
  }

  return user.job_title?.trim() || roleLabel(user.role);
}

type CurrentUserContextValue = {
  user: CurrentUser | null;
  loading: boolean;
  /** Re-read who is signed in, e.g. after they change their profile. */
  refresh: () => Promise<void>;
};

const CurrentUserContext = createContext<CurrentUserContextValue>({
  user: null,
  loading: true,
  refresh: async () => {},
});

export function CurrentUserProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const response = await api.get<CurrentUser>("/auth/me");

      setUser(response.data);
    } catch {
      // The page's own requests handle a lapsed sign-in; the shell just
      // shows no name rather than an error.
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ user, loading, refresh }),
    [user, loading, refresh],
  );

  return (
    <CurrentUserContext.Provider value={value}>
      {children}
    </CurrentUserContext.Provider>
  );
}

export function useCurrentUser() {
  return useContext(CurrentUserContext);
}
