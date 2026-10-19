"use client";

import { useEffect, useState } from "react";

import { initialsOf } from "@/components/CurrentUserProvider";
import api from "@/lib/api";

const avatarCache = new Map<string, Promise<string | null>>();
const avatarUrls = new Map<string, string>();

async function loadAvatar(userId: string): Promise<string | null> {
  const cached = avatarCache.get(userId);
  if (cached) return cached;

  const request = api
    .get(`/users/${userId}/avatar`, { responseType: "blob" })
    .then((response) => {
      const url = URL.createObjectURL(response.data);
      avatarUrls.set(userId, url);
      return url;
    })
    .catch(() => {
      // No photo, or the request failed: show initials instead.
      avatarCache.delete(userId);
      return null;
    });

  avatarCache.set(userId, request);
  return request;
}

/** Invalidate a photo after it has been changed. */
export function clearUserAvatarCache(userId: string) {
  avatarCache.delete(userId);

  const oldUrl = avatarUrls.get(userId);
  if (oldUrl) {
    URL.revokeObjectURL(oldUrl);
    avatarUrls.delete(userId);
  }

  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("funeralos-avatar-updated", { detail: { userId } }),
    );
  }
}

/** A person's photo, or their initials when they have not set one. */
export function UserAvatar({
  name,
  src,
  userId,
  size = 36,
  color,
}: {
  name: string | null | undefined;
  src?: string | null;
  userId?: string | null;
  size?: number;
  color?: string;
}) {
  const [loadedSrc, setLoadedSrc] = useState<string | null>(src ?? null);

  useEffect(() => {
    if (src) {
      setLoadedSrc(src);
      return;
    }

    if (!userId) {
      setLoadedSrc(null);
      return;
    }

    let cancelled = false;

    const load = () => {
      setLoadedSrc(null);
      void loadAvatar(userId).then((url) => {
        if (!cancelled) setLoadedSrc(url);
      });
    };

    load();

    const onAvatarUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ userId: string }>).detail;
      if (detail?.userId === userId) load();
    };

    window.addEventListener("funeralos-avatar-updated", onAvatarUpdated);

    return () => {
      cancelled = true;
      window.removeEventListener(
        "funeralos-avatar-updated",
        onAvatarUpdated,
      );
    };
  }, [src, userId]);

  const style = { width: size, height: size };

  if (loadedSrc) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={loadedSrc}
        alt=""
        style={style}
        className="shrink-0 rounded-full object-cover"
      />
    );
  }

  return (
    <span
      aria-hidden="true"
      style={{
        ...style,
        backgroundColor: color || "var(--fos-primary)",
        color: color ? "#ffffff" : "var(--fos-on-primary)",
        fontSize: Math.max(11, Math.round(size * 0.38)),
      }}
      className="flex shrink-0 items-center justify-center rounded-full font-semibold"
    >
      {initialsOf(name)}
    </span>
  );
}
