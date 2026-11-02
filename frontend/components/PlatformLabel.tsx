"use client";

import { useBranding } from "@/components/BrandingProvider";
import { useCurrentUser } from "@/components/CurrentUserProvider";

/** "Funeral Platform" for funeral businesses, "Business Management Platform" otherwise. */
export function usePlatformLabel() {
  const { access, loading } = useCurrentUser();
  if (loading && !access) return "";
  return access?.business_type === "funeral" ? "Funeral Platform" : "Business Management Platform";
}

/** Top-right identity: business name with the platform type beneath it. */
export function BusinessIdentity({ align = "right" }: { align?: "left" | "right" }) {
  const { branding } = useBranding();
  const label = usePlatformLabel();
  const name = branding?.name || "LINDA";
  return (
    <div className={`min-w-0 leading-tight ${align === "right" ? "text-right" : "text-left"}`}>
      <p className="truncate text-sm font-semibold text-[var(--fos-text)]">{name}</p>
      {label && <p className="truncate text-xs text-[var(--fos-text-muted)]">{label}</p>}
    </div>
  );
}
