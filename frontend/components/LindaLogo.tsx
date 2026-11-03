/**
 * LINDA brand marks.
 *
 * The icon is a geometric L: one upright, one foot, joined at a corner,
 * with a gold node where the work connects. It is deliberately plain so it
 * stays readable at favicon size, and it carries no industry imagery.
 */

type MarkProps = {
  size?: number;
  /** "tile" draws the navy rounded square; "bare" draws only the L. */
  variant?: "tile" | "bare";
  className?: string;
  title?: string;
};

export function LindaMark({
  size = 36,
  variant = "tile",
  className,
  title = "LINDA",
}: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label={title}
      className={className}
    >
      {variant === "tile" && (
        <rect width="64" height="64" rx="15" fill="#101D2B" />
      )}
      <path
        d="M22 14 V45 H43"
        fill="none"
        stroke={variant === "tile" ? "#FFFFFF" : "currentColor"}
        strokeWidth="7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="46" cy="45" r="5.5" fill="#D6A85F" />
    </svg>
  );
}

type WordmarkProps = {
  /** Colour of the letters. Defaults to the current text colour. */
  className?: string;
  size?: "sm" | "md" | "lg";
};

const WORD_SIZE = { sm: "text-lg", md: "text-xl", lg: "text-3xl" } as const;

export function LindaWordmark({ className = "", size = "md" }: WordmarkProps) {
  return (
    <span
      className={`font-semibold tracking-[0.22em] ${WORD_SIZE[size]} ${className}`}
    >
      LINDA
    </span>
  );
}

export function LindaLockup({
  markSize = 36,
  className = "",
  wordClassName = "",
  size = "md",
}: {
  markSize?: number;
  className?: string;
  wordClassName?: string;
  size?: WordmarkProps["size"];
}) {
  return (
    <span className={`inline-flex items-center gap-3 ${className}`}>
      <LindaMark size={markSize} />
      <LindaWordmark className={wordClassName} size={size} />
    </span>
  );
}
