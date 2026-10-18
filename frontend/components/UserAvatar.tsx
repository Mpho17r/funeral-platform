"use client";

import { initialsOf } from "@/components/CurrentUserProvider";

/** A person's photo, or their initials when they have not set one. */
export function UserAvatar({
  name,
  src,
  size = 36,
  color,
}: {
  name: string | null | undefined;
  src?: string | null;
  size?: number;
  color?: string;
}) {
  const style = { width: size, height: size };

  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
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
