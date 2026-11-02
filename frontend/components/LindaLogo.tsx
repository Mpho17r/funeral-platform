type Props = {
  size?: number;
  /** "light" for use on navy backgrounds, "dark" for light backgrounds. */
  tone?: "light" | "dark";
  showWordmark?: boolean;
  className?: string;
};

/** LINDA geometric "L" mark with optional wordmark. No imagery, readable at 16px. */
export function LindaMark({ size = 36, tone = "dark" }: { size?: number; tone?: "light" | "dark" }) {
  const bg = tone === "light" ? "#FFFFFF" : "#101D2B";
  const fg = tone === "light" ? "#101D2B" : "#FFFFFF";
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" className="shrink-0">
      <rect width="64" height="64" rx="14" fill={bg} />
      <path d="M20 14h9v28h19v8H20z" fill={fg} />
      <rect x="34" y="14" width="10" height="8" rx="2" fill="#D6A85F" />
    </svg>
  );
}

export default function LindaLogo({ size = 36, tone = "dark", showWordmark = true, className = "" }: Props) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LindaMark size={size} tone={tone} />
      {showWordmark && (
        <span
          className={`font-semibold tracking-[0.18em] ${tone === "light" ? "text-white" : "text-slate-900"}`}
          style={{ fontSize: Math.round(size * 0.5) }}
        >
          LINDA
        </span>
      )}
    </span>
  );
}
