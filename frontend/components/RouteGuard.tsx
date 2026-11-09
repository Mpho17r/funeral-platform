"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Lock } from "lucide-react";

import { holds, permissionForPath } from "@/lib/access";
import { useCurrentUser } from "@/components/CurrentUserProvider";

/**
 * Shows a clear message instead of a half-working screen when the person
 * opens a page outside their work. The server already refuses the data;
 * this is the friendly face of that.
 */
export function RouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { can, user, loading } = useCurrentUser();

  // Defence in depth: never render protected route children while the
  // session is unresolved or the account is not authenticated.
  if (loading || !user) return null;

  const needed = permissionForPath(pathname);

  if (needed && !holds(needed, can)) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 px-6 py-24 text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--fos-surface-muted)] text-[var(--fos-text-muted)]">
          <Lock size={26} />
        </span>
        <h1 className="text-xl font-bold text-[var(--fos-text)]">
          This is outside your work
        </h1>
        <p className="text-sm text-[var(--fos-text-muted)]">
          Your account does not include this part of LINDA. If you
          need it for your job, ask your manager to update your access.
        </p>
        <Link
          href="/dashboard"
          className="mt-2 rounded-lg bg-[var(--fos-primary)] px-4 py-2 text-sm font-semibold text-[var(--fos-on-primary)]"
        >
          Back to my dashboard
        </Link>
      </div>
    );
  }

  return <>{children}</>;
}
