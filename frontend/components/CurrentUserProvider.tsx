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
  business_name: string | null;
  avatar_updated_at: string | null;
  member_since: string | null;
};

export type Access = {
  role: string;
  work_area: string;
  permissions: string[];
};

const ROLE_LABELS: Record<string, string> = {
  main_admin: "Main administrator",
  manager: "Manager",
  staff: "Staff member",
  mortuary: "Mortuary team",
  finance: "Finance and memberships",
  operations: "Funeral operations",
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
  /** The profile photo, ready to use as an image source, or null. */
  avatarUrl: string | null;
  /** Re-read who is signed in, e.g. after they change their profile. */
  refresh: () => Promise<void>;
  /** What the person may do. Null until it has loaded. */
  access: Access | null;
  /**
   * Whether the person holds a permission. Until access has loaded it
   * says yes, so a slow request never hides the whole app; the server
   * enforces the real rule either way.
   */
  can: (permission: string) => boolean;
};

const CurrentUserContext = createContext<CurrentUserContextValue>({
  user: null,
  loading: true,
  avatarUrl: null,
  refresh: async () => {},
  access: null,
  can: () => true,
});

export function CurrentUserProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [access, setAccess] = useState<Access | null>(null);

  const refresh = useCallback(async () => {
    try {
      const response = await api.get<CurrentUser>("/auth/me");

      setUser(response.data);

      try {
        const mine = await api.get<Access>("/users/me/access");

        setAccess(mine.data);
      } catch {
        setAccess(null);
      }
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

  // The photo needs the sign-in token, so it is fetched as a file and shown
  // from a local address. It is fetched again only when it changes.
  const userId = user?.user_id;
  const avatarVersion = user?.avatar_updated_at;

  useEffect(() => {
    if (!userId || !avatarVersion) {
      setAvatarUrl(null);
      return;
    }

    let cancelled = false;
    let created: string | null = null;

    api
      .get(`/users/${userId}/avatar`, { responseType: "blob" })
      .then((response) => {
        if (cancelled) {
          return;
        }

        created = URL.createObjectURL(response.data);
        setAvatarUrl(created);
      })
      .catch(() => {
        if (!cancelled) {
          setAvatarUrl(null);
        }
      });

    return () => {
      cancelled = true;

      if (created) {
        URL.revokeObjectURL(created);
      }
    };
  }, [userId, avatarVersion]);

  const value = useMemo(() => {
    const held = access ? new Set(access.permissions) : null;

    return {
      user,
      loading,
      avatarUrl,
      refresh,
      access,
      can: (permission: string) => (held ? held.has(permission) : true),
    };
  }, [user, loading, avatarUrl, refresh, access]);

  return (
    <CurrentUserContext.Provider value={value}>
      {children}
    </CurrentUserContext.Provider>
  );
}

export function useCurrentUser() {
  return useContext(CurrentUserContext);
}
