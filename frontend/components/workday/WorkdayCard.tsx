"use client";

import { useEffect, useState } from "react";
import {
  Clock3,
  Coffee,
  LogIn,
  LogOut,
  Loader2,
  Moon,
  Sun,
  Sunrise,
  Utensils,
} from "lucide-react";

type BreakType = "tea" | "lunch";

export type WorkdayProps = {
  firstName: string;
  loaded: boolean;
  checkedInAt: string | null;
  currentBreak: { break_type: BreakType; started_at: string } | null;
  breakExpiresAt: string | null;
  warning: boolean;
  action: string | null;
  onCheckIn: () => void;
  onCheckOut: () => void;
  onStartBreak: (type: BreakType) => void;
  onEndBreak: () => void;
};

type Mode = "idle" | "working" | "tea" | "lunch";

const WORKDAY_SECONDS = 8 * 3600;
const CONFETTI = [
  "#22c55e", "#f59e0b", "#3b82f6", "#ec4899", "#a855f7", "#14b8a6",
];

function pad(n: number) {
  return String(n).padStart(2, "0");
}

function clock(totalSeconds: number) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0
    ? `${h}:${pad(m)}:${pad(s % 60)}`
    : `${pad(m)}:${pad(s % 60)}`;
}

function greeting(hour: number) {
  if (hour < 5) return { text: "Working late", Icon: Moon };
  if (hour < 12) return { text: "Good morning", Icon: Sunrise };
  if (hour < 18) return { text: "Good afternoon", Icon: Sun };
  return { text: "Good evening", Icon: Moon };
}

const THEME: Record<Mode, { tint: string; accent: string; label: string }> = {
  idle: {
    tint: "var(--fos-primary)",
    accent: "var(--fos-primary)",
    label: "Not checked in",
  },
  working: { tint: "#10b981", accent: "#10b981", label: "At work" },
  tea: { tint: "#f43f5e", accent: "#f43f5e", label: "Tea break" },
  lunch: { tint: "#f59e0b", accent: "#f59e0b", label: "Lunch break" },
};

function Confetti() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 flex items-center justify-center"
    >
      {Array.from({ length: 22 }).map((_, i) => {
        const angle = (i / 22) * Math.PI * 2;
        const dist = 90 + (i % 5) * 28;

        return (
          <span
            key={i}
            className="fos-anim absolute h-2 w-2 rounded-sm"
            style={
              {
                background: CONFETTI[i % CONFETTI.length],
                "--dx": `${Math.cos(angle) * dist}px`,
                "--dy": `${Math.sin(angle) * dist - 20}px`,
                "--rot": `${(i * 47) % 360}deg`,
                animation: `fos-confetti ${0.9 + (i % 4) * 0.12}s ease-out forwards`,
              } as React.CSSProperties
            }
          />
        );
      })}
    </div>
  );
}

function Steam({ color }: { color: string }) {
  return (
    <div
      aria-hidden="true"
      className="absolute -top-5 left-1/2 flex -translate-x-1/2 gap-1.5"
    >
      {[0, 0.5, 1].map((delay) => (
        <span
          key={delay}
          className="fos-anim h-4 w-1 rounded-full opacity-0"
          style={{
            background: color,
            animation: `fos-steam 2s ease-in-out ${delay}s infinite`,
          }}
        />
      ))}
    </div>
  );
}

function Ring({
  size,
  progress,
  color,
  children,
  urgent = false,
  spin = false,
}: {
  size: number;
  progress: number;
  color: string;
  children: React.ReactNode;
  urgent?: boolean;
  spin?: boolean;
}) {
  const stroke = 9;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;

  return (
    <div
      className={`fos-anim relative flex shrink-0 items-center justify-center rounded-full ${
        urgent ? "" : ""
      }`}
      style={{
        width: size,
        height: size,
        animation: urgent
          ? "fos-urgent 1.2s ease-out infinite"
          : "fos-breathe 4s ease-in-out infinite",
      }}
    >
      {spin && (
        <span
          aria-hidden="true"
          className="fos-anim absolute inset-0 rounded-full"
          style={{
            background: `conic-gradient(from 0deg, transparent 0 80%, ${color}55 100%)`,
            animation: "fos-sweep 6s linear infinite",
            mask: `radial-gradient(circle, transparent ${r - 6}px, #000 ${r - 5}px)`,
            WebkitMask: `radial-gradient(circle, transparent ${r - 6}px, #000 ${r - 5}px)`,
          }}
        />
      )}
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="absolute inset-0 -rotate-90"
        aria-hidden="true"
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          className="text-black/10 dark:text-white/10"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - Math.min(1, Math.max(0, progress)))}
          style={{ transition: "stroke-dashoffset 1s linear" }}
        />
      </svg>
      <div className="relative text-center">{children}</div>
    </div>
  );
}

export default function WorkdayCard(props: WorkdayProps) {
  const {
    firstName,
    loaded,
    checkedInAt,
    currentBreak,
    breakExpiresAt,
    warning,
    action,
  } = props;

  const mode: Mode = !checkedInAt
    ? "idle"
    : currentBreak
      ? currentBreak.break_type
      : "working";

  const [now, setNow] = useState(() => Date.now());
  const [celebration, setCelebration] = useState<{
    key: number;
    text: string;
  } | null>(null);
  const [prev, setPrev] = useState({ mode, loaded });

  // Celebrate a change the person just made, never what loads on arrival.
  if (prev.mode !== mode || prev.loaded !== loaded) {
    const changed = prev.loaded && loaded && prev.mode !== mode;
    setPrev({ mode, loaded });

    if (changed) {
      const text =
        prev.mode === "idle"
          ? "Checked in. Have a great day!"
          : mode === "idle"
            ? "Checked out. See you next time!"
            : mode === "working"
              ? "Welcome back!"
              : mode === "lunch"
                ? "Enjoy your lunch!"
                : "Enjoy your tea!";

      setCelebration((c) => ({ key: (c?.key ?? 0) + 1, text }));
    }
  }

  useEffect(() => {
    if (!celebration) return;
    const timer = window.setTimeout(() => setCelebration(null), 2600);
    return () => window.clearTimeout(timer);
  }, [celebration]);

  useEffect(() => {
    if (!checkedInAt) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [checkedInAt]);

  const theme = THEME[mode];
  const hello = greeting(new Date(now).getHours());
  const busy = action !== null;

  const worked = checkedInAt
    ? (now - new Date(checkedInAt).getTime()) / 1000
    : 0;

  let breakLeft = 0;
  let breakTotal = 1;
  if (currentBreak && breakExpiresAt) {
    const start = new Date(currentBreak.started_at).getTime();
    const end = new Date(breakExpiresAt).getTime();
    breakTotal = Math.max(1, (end - start) / 1000);
    breakLeft = Math.max(0, (end - now) / 1000);
  }

  const overdue = Boolean(currentBreak && breakExpiresAt && breakLeft <= 0);
  const urgent = warning || overdue;
  const accent = urgent && currentBreak ? "#ef4444" : theme.accent;

  const btn =
    "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition active:scale-95 disabled:cursor-not-allowed disabled:opacity-60";
  const quiet = `${btn} border border-[var(--fos-border)] bg-[var(--fos-surface)] text-[var(--fos-text)] hover:bg-[var(--fos-surface-muted)]`;

  const spin = (k: string, icon: React.ReactNode) =>
    action === k ? <Loader2 size={16} className="animate-spin" /> : icon;

  return (
    <section
      aria-label="My workday"
      className="relative overflow-hidden rounded-3xl border border-[var(--fos-border)] p-5 shadow-sm sm:p-7"
      style={{
        background: `linear-gradient(135deg, color-mix(in srgb, ${accent} 16%, var(--fos-surface)) 0%, var(--fos-surface) 70%)`,
        transition: "background 0.6s",
      }}
    >
      {celebration && (
        <>
          {mode !== "idle" && <Confetti key={celebration.key} />}
          <p
            key={`t-${celebration.key}`}
            role="status"
            className="fos-anim absolute left-1/2 top-3 z-10 -translate-x-1/2 rounded-full px-4 py-1.5 text-sm font-semibold text-white shadow-lg"
            style={{
              background: accent,
              animation: "fos-pop 0.5s ease-out both",
            }}
          >
            {celebration.text}
          </p>
        </>
      )}

      <div className="flex flex-col items-center gap-6 md:flex-row md:justify-between">
        {/* left: who and what */}
        <div className="w-full text-center md:w-auto md:text-left">
          <p className="flex items-center justify-center gap-2 text-sm text-[var(--fos-text-muted)] md:justify-start">
            <hello.Icon size={16} />
            {hello.text}
          </p>
          <h2 className="mt-1 text-2xl font-bold text-[var(--fos-text)] sm:text-3xl">
            {firstName || "there"}
          </h2>

          <span
            className="mt-3 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold"
            style={{
              background: `color-mix(in srgb, ${accent} 16%, transparent)`,
              color: accent,
            }}
          >
            <span
              className="fos-anim h-2 w-2 rounded-full"
              style={{
                background: accent,
                animation:
                  mode === "idle" ? "none" : "fos-breathe 1.6s ease-in-out infinite",
              }}
            />
            {urgent && currentBreak
              ? overdue
                ? "Break is over"
                : "Break almost over"
              : theme.label}
          </span>

          <p className="mt-3 max-w-xs text-sm text-[var(--fos-text-muted)]">
            {mode === "idle" &&
              "Tap the button to start your workday and let the team know you are in."}
            {mode === "working" &&
              `Checked in at ${new Date(checkedInAt!).toLocaleTimeString("en-ZA", { hour: "2-digit", minute: "2-digit", hour12: false })}. Remember to take your breaks.`}
            {(mode === "lunch" || mode === "tea") &&
              (overdue
                ? "Your break time is up. Tap “I'm back” when you are at your desk."
                : "Your team can see you are on a break. Relax, we will let you know when it is nearly over.")}
          </p>
        </div>

        {/* middle: the orb */}
        <div className="flex shrink-0 items-center justify-center">
          {mode === "idle" ? (
            <div className="relative flex h-44 w-44 items-center justify-center">
              {[0, 1.2].map((delay) => (
                <span
                  key={delay}
                  aria-hidden="true"
                  className="fos-anim absolute inset-4 rounded-full"
                  style={{
                    background: accent,
                    opacity: 0,
                    animation: loaded
                      ? `fos-ripple 2.4s ease-out ${delay}s infinite`
                      : "none",
                  }}
                />
              ))}
              <button
                type="button"
                onClick={props.onCheckIn}
                disabled={busy || !loaded}
                aria-label="Check in"
                className="fos-anim relative flex h-32 w-32 flex-col items-center justify-center gap-1 rounded-full text-[var(--fos-on-primary)] shadow-xl transition hover:scale-105 active:scale-95 disabled:opacity-60"
                style={{
                  background: accent,
                  animation: "fos-breathe 3s ease-in-out infinite",
                }}
              >
                {action === "check-in" ? (
                  <Loader2 size={30} className="animate-spin" />
                ) : (
                  <LogIn size={30} />
                )}
                <span className="text-sm font-bold">Check in</span>
              </button>
            </div>
          ) : mode === "working" ? (
            <Ring
              size={176}
              color={accent}
              progress={worked / WORKDAY_SECONDS}
              spin
            >
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--fos-text-muted)]">
                On the clock
              </p>
              <p className="text-3xl font-bold tabular-nums text-[var(--fos-text)]">
                {clock(worked)}
              </p>
              <p className="text-[11px] text-[var(--fos-text-muted)]">
                of an 8 hour day
              </p>
            </Ring>
          ) : (
            <Ring
              size={176}
              color={accent}
              progress={breakLeft / breakTotal}
              urgent={urgent}
            >
              <div className="relative mx-auto mb-1 flex h-9 w-9 items-center justify-center">
                <Steam color={accent} />
                <span
                  className="fos-anim"
                  style={{ animation: "fos-float 2.4s ease-in-out infinite" }}
                >
                  {mode === "lunch" ? (
                    <Utensils size={28} style={{ color: accent }} />
                  ) : (
                    <Coffee size={28} style={{ color: accent }} />
                  )}
                </span>
              </div>
              <p
                className="text-3xl font-bold tabular-nums"
                style={{ color: urgent ? accent : "var(--fos-text)" }}
              >
                {clock(breakLeft)}
              </p>
              <p className="text-[11px] text-[var(--fos-text-muted)]">
                {overdue ? "over time" : "left"}
              </p>
            </Ring>
          )}
        </div>

        {/* right: actions */}
        <div className="flex w-full flex-col gap-2 md:w-48">
          {mode === "working" && (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => props.onStartBreak("lunch")}
                className={quiet}
              >
                {spin("lunch", <Utensils size={16} />)}
                Lunch break
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => props.onStartBreak("tea")}
                className={quiet}
              >
                {spin("tea", <Coffee size={16} />)}
                Tea break
              </button>
            </>
          )}

          {(mode === "lunch" || mode === "tea") && (
            <button
              type="button"
              disabled={busy}
              onClick={props.onEndBreak}
              className={`${btn} text-white shadow-md hover:opacity-90`}
              style={{ background: accent }}
            >
              {spin("end-break", <Clock3 size={16} />)}
              I&apos;m back
            </button>
          )}

          {mode !== "idle" && (
            <button
              type="button"
              disabled={busy}
              onClick={props.onCheckOut}
              className={`${btn} border border-red-300/60 bg-red-500/10 text-red-600 hover:bg-red-500/20 dark:text-red-300`}
            >
              {spin("check-out", <LogOut size={16} />)}
              Check out
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
