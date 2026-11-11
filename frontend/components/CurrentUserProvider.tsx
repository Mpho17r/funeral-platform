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
import { getToken, removeToken } from "@/lib/auth";

export type CurrentUser = {
  user_id: string;
  business_id: string;
  role: string;
  full_name: string | null;
  email: string | null;
  /** False until the person follows the emailed link; null if unknown. */
  email_verified: boolean | null;
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
  /** "funeral" (the full platform) or "general" (any other business). */
  business_type?: string;
  /** False when the business has switched the membership scheme off. */
  membership_enabled?: boolean;
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
  /** True when the server could not be reached to validate the session. */
  authUnavailable: boolean;
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
  /** A general business: no funeral screens, money and tasks instead. */
  isGeneral: boolean;
  /** True when the account's access details could not be loaded. */
  accessFailed: boolean;
  /** Does this business run a membership scheme? */
  membershipEnabled: boolean;
};

const CurrentUserContext = createContext<CurrentUserContextValue>({
  user: null,
  loading: true,
  authUnavailable: false,
  avatarUrl: null,
  refresh: async () => {},
  access: null,
  can: () => true,
  isGeneral: false,
  accessFailed: false,
  membershipEnabled: true,
});

export function CurrentUserProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [authUnavailable, setAuthUnavailable] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [access, setAccess] = useState<Access | null>(null);
  const [accessFailed, setAccessFailed] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setAuthUnavailable(false);

    // Do not make an unauthenticated request and wait for its 401. This
    // also lets the protected shell decide before rendering any app chrome.
    if (!getToken()) {
      setUser(null);
      setAccess(null);
      setAccessFailed(false);
      setLoading(false);
      return;
    }

    try {
      const response = await api.get<CurrentUser>("/auth/me");

      // A pre-existing session may predate mandatory email verification.
      // Keep the identity endpoint available for verification UX, but never
      // hydrate the business workspace for an unverified account.
      if (response.data.email_verified === false) {
        removeToken();
        setUser(null);
        setAccess(null);
        setAccessFailed(false);
        return;
      }

      setUser(response.data);

      try {
        const mine = await api.get<Access>("/users/me/access");
        setAccess(mine.data);
        setAccessFailed(false);
      } catch (error) {
        const status = (
          error as { response?: { status?: number } }
        ).response?.status;

        setAccess(null);

        if (status === 401) {
          // The session may expire between /auth/me and the access lookup.
          setUser(null);
          removeToken();
        } else {
          // Keep the authenticated identity, but fail closed for permissions.
          setAccessFailed(true);
        }
      }
    } catch (error) {
      const status = (
        error as { response?: { status?: number } }
      ).response?.status;

      setUser(null);
      setAccess(null);
      setAccessFailed(false);

      if (status === 401) {
        // Only an explicitly rejected credential is cleared. Network errors
        // must not silently sign a customer out.
        removeToken();
      } else {
        setAuthUnavailable(true);
      }
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
      authUnavailable,
      avatarUrl,
      refresh,
      access,
      // While loading, say yes so a slow request never hides the app. If the
      // details could not be loaded at all, say no: showing every screen
      // (funeral ones included) to a business that may not have them is worse.
      can: (permission: string) =>
        held ? held.has(permission) : !accessFailed,
      accessFailed,
      isGeneral: access?.business_type === "general",
      // Memberships belong to the funeral side only: a general business
      // never has them, whatever the stored flag says.
      membershipEnabled:
        access?.business_type !== "general" &&
        access?.membership_enabled !== false,
    };
  }, [user, loading, authUnavailable, avatarUrl, refresh, access, accessFailed]);

  return (
    <CurrentUserContext.Provider value={value}>
      {children}
    </CurrentUserContext.Provider>
  );
}

export function useCurrentUser() {
  return useContext(CurrentUserContext);
}
