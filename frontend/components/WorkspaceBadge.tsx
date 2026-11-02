"use client";

import { useBranding } from "@/components/BrandingProvider";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { PLATFORM_NAME, platformLabel } from "@/lib/platform";

/**
 * Top-right identity: the business name, with the kind of platform it runs
 * on written underneath ("Funeral Platform" or "Business Management
 * Platform"). Nothing is guessed while the account is still loading.
 */
export function WorkspaceBadge({ compact = false }: { compact?: boolean }) {
  const { branding, logoObjectUrl } = useBranding();
  const { access, isGeneral } = useCurrentUser();

  const name = branding?.name || PLATFORM_NAME;
  const label = access ? platformLabel(isGeneral) : "";

  return (
    <div
      className="flex min-w-0 items-center gap-2.5"
      data-testid="workspace-badge"
    >
      {logoObjectUrl && !compact && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={logoObjectUrl}
          alt=""
          className="h-8 w-8 shrink-0 rounded-md bg-white object-contain ring-1 ring-[var(--fos-border)]"
        />
      )}

      <div className="min-w-0 text-right leading-tight">
        <p className="truncate text-sm font-semibold text-[var(--fos-text)]">
          {name}
        </p>
        <p
          className="truncate text-[10px] font-semibold uppercase tracking-[0.12em]"
          style={{ color: "var(--linda-gold-text)", minHeight: "0.9rem" }}
        >
          {label}
        </p>
      </div>
    </div>
  );
}
