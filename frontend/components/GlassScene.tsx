"use client";

import { useEffect } from "react";

import { useTheme } from "@/components/ThemeProvider";

/**
 * The "Glass" look, open to every business: a dawn scene behind the app with
 * frosted panels on top. It sits below everything (the tenant watermark is a
 * separate layer above the page) and is tinted by the business's brand colours.
 */
export function GlassScene({
  userId,
  serverStyle,
}: {
  userId: string | null;
  serverStyle?: string | null;
}) {
  const { glassActive, loadStyleFor } = useTheme();

  useEffect(() => {
    loadStyleFor(userId, serverStyle);
    // Only when who is signed in changes: our own saves must not be undone
    // by an older copy of the profile.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, loadStyleFor]);

  if (!glassActive) return null;

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
      style={{
        background:
          "linear-gradient(180deg, #3f5251 0%, #6f7a62 30%, #c8a56a 56%, #8a6c40 76%, #3a3022 100%)",
      }}
    >
      {/* Brand-coloured glow: the business's secondary colour lights the sky */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 55% 38% at 64% 40%, color-mix(in srgb, var(--brand-secondary) 55%, transparent), transparent 70%)",
        }}
      />
      <div
        className="absolute"
        style={{
          inset: "-10% 0 30% 0",
          filter: "blur(10px)",
          mixBlendMode: "screen",
          background:
            "conic-gradient(from 168deg at 64% -6%, transparent 0deg, color-mix(in srgb, var(--brand-secondary) 30%, transparent) 6deg, transparent 12deg, color-mix(in srgb, var(--brand-secondary) 22%, transparent) 19deg, transparent 26deg, color-mix(in srgb, var(--brand-secondary) 28%, transparent) 33deg, transparent 41deg, color-mix(in srgb, var(--brand-secondary) 18%, transparent) 49deg, transparent 58deg)",
        }}
      />
      <svg
        viewBox="0 0 1440 520"
        preserveAspectRatio="none"
        className="absolute bottom-0 left-0 right-0 h-[45vh] w-full"
      >
        <path d="M0 250 C 160 190, 300 230, 460 170 S 760 120, 940 190 S 1260 150, 1440 210 L1440 520 L0 520 Z" fill="#8a7a4e" opacity="0.6" style={{ filter: "blur(3px)" }} />
        <path d="M0 330 C 200 270, 360 330, 560 280 S 900 230, 1100 290 S 1340 300, 1440 270 L1440 520 L0 520 Z" fill="#5e5035" opacity="0.8" style={{ filter: "blur(2px)" }} />
        <path d="M0 420 C 240 370, 420 430, 700 390 S 1120 350, 1440 400 L1440 520 L0 520 Z" fill="#2e2619" />
      </svg>
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at 50% 40%, rgba(0,0,0,0) 45%, rgba(24,16,6,0.40) 100%)",
        }}
      />
    </div>
  );
}
