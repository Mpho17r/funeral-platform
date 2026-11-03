"use client";

import { TriangleAlert } from "lucide-react";

import { useCurrentUser } from "@/components/CurrentUserProvider";

/**
 * Shown when the account's access details could not be loaded. Without
 * them the app cannot tell which screens belong to this business, so it
 * says so instead of guessing.
 */
export function AccessWarning() {
  const { accessFailed, refresh } = useCurrentUser();

  if (!accessFailed) {
    return null;
  }

  return (
    <div
      role="alert"
      className="m-4 flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"
    >
      <TriangleAlert size={18} className="mt-0.5 shrink-0" />
      <div className="flex-1">
        <p className="font-semibold">We couldn&apos;t load your account details.</p>
        <p className="mt-1">
          Some screens are hidden until they load. If you have just updated
          LINDA, run <code>python3 -m alembic upgrade head</code> and{" "}
          <code>python3 -m app.seed_permissions</code> in the backend folder,
          then restart the backend.
        </p>
        <button
          type="button"
          onClick={() => void refresh()}
          className="mt-2 rounded-md border border-amber-400 bg-white px-3 py-1 font-medium hover:bg-amber-100"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
