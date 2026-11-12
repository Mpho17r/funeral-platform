
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
  email_verified: boolean | null;
  job_title: string | null;
  branch_id: string | null;
  branch_name: string | null;
  business_name: string | null;
  avatar_updated_at: string | null;
  ui_style?: string | null;
  member_since: string | null;
};

export type Access = {
  role: string;
  work_area: string;
  business_type?: string;
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

 export function roleLabel(role: string | null | undefined): string {
  if (!role) {
    return "";
  }

  return (
    ROLE_LABELS[role] ??
    role.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase())
  );
}

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

 export function titleOf(
  user: Pick<CurrentUser, "job_title" | "role"> | null,
): string {
  if (!user) {
    return "";
  }

  return user.job_title?.trim() || roleLabel(user.role);
}

type RefreshOptions = {
  silent?: boolean;
};

type CurrentUserContextValue = {
  user: CurrentUser | null;
  loading: boolean;
   authUnavailable: boolean;
  avatarUrl: string | null;
  refresh: (options?: RefreshOptions) => Promise<void>;
   access: Access | null;
  can: (permission: string) => boolean;
   isGeneral: boolean;
  accessFailed: boolean;
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

  const refresh = useCallback(
    async (options?: RefreshOptions) => {
      const silent = options?.silent === true;

      // Silent refreshes must not replace the workspace with a loading screen.
      if (!silent) {
        setLoading(true);
        setAuthUnavailable(false);
      }

      // Do not make an unauthenticated request.
      if (!getToken()) {
        setUser(null);
        setAccess(null);
        setAccessFailed(false);
        setAuthUnavailable(false);
        setLoading(false);
        return;
      }

      try {
        const response = await api.get<CurrentUser>("/auth/me");

        // Never hydrate the workspace for an unverified account.
        if (response.data.email_verified === false) {
          removeToken();
          setUser(null);
          setAccess(null);
          setAccessFailed(false);
          setAuthUnavailable(false);
          return;
        }

        setUser(response.data);
        setAuthUnavailable(false);

        try {
          const mine = await api.get<Access>("/users/me/access");

          setAccess(mine.data);
          setAccessFailed(false);
        } catch (error) {
          const status = (
            error as { response?: { status?: number } }
          ).response?.status;

          if (status === 401) {
            // The session may expire between the two requests.
            setUser(null);
            setAccess(null);
            setAccessFailed(false);
            removeToken();
          } else if (!silent) {
            // Normal refreshes fail closed if access cannot be loaded.
            setAccess(null);
            setAccessFailed(true);
          }

          // During a silent refresh, retain the last known access
          // information if this request fails temporarily.
        }
      } catch (error) {
        const status = (
          error as { response?: { status?: number } }
        ).response?.status;

        if (status === 401) {
          // An explicitly rejected credential must always be cleared.
          setUser(null);
          setAccess(null);
          setAccessFailed(false);
          setAuthUnavailable(false);
          removeToken();
        } else if (!silent) {
          // A normal refresh cannot verify the session.
          setUser(null);
          setAccess(null);
          setAccessFailed(false);
          setAuthUnavailable(true);
        }

        // A temporary error during a silent refresh preserves the
        // existing authenticated workspace.
      } finally {
        if (!silent) {
          setLoading(false);
        }
      }
    },
    [],
  );

    useEffect(() => {
    let cancelled = false;

    queueMicrotask(() => {
      if (!cancelled) {
        void refresh();
      }
    });

    return () => {
      cancelled = true;
    };
  }, [refresh]);

  // Fetch the profile photo using the authenticated API client.
  const userId = user?.user_id;
  const avatarVersion = user?.avatar_updated_at;

    useEffect(() => {
    let cancelled = false;

    if (!userId || !avatarVersion) {
      queueMicrotask(() => {
        if (!cancelled) {
          setAvatarUrl(null);
        }
      });

      return () => {
        cancelled = true;
      };
    }
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
       can: (permission: string) =>
        held ? held.has(permission) : !accessFailed,
      accessFailed,
       isGeneral: access?.business_type === "general",
      membershipEnabled:
        access?.business_type !== "general" &&
        access?.membership_enabled !== false,
    };
  }, [
    user,
    loading,
    authUnavailable,
    avatarUrl,
    refresh,
    access,
    accessFailed,
  ]);

  return (
    <CurrentUserContext.Provider value={value}>
      {children}
    </CurrentUserContext.Provider>
  );
}

export function useCurrentUser() {
  return useContext(CurrentUserContext);
}
