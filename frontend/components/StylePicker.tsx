"use client";

import { useTheme } from "@/components/ThemeProvider";

const OPTIONS = [
  {
    id: "default" as const,
    name: "Standard",
    hint: "Clean, light and simple.",
    preview: "linear-gradient(135deg,#f5f6f8,#e2e6ec)",
  },
  {
    id: "glass" as const,
    name: "Glass",
    hint: "Frosted panels over a soft dawn scene.",
    preview: "linear-gradient(180deg,#1c2a2d,#8c7c5c 70%,#2c2b22)",
  },
];

/** The two looks as tappable cards. Used on first sign-in and in settings. */
export function StyleChoices({ preview = false }: { preview?: boolean }) {
  const { uiStyle, setUiStyle, previewUiStyle } = useTheme();

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {OPTIONS.map((o) => (
        <button
          key={o.id}
          type="button"
          aria-pressed={uiStyle === o.id}
          onClick={() => (preview ? previewUiStyle(o.id) : setUiStyle(o.id))}
          className={`flex flex-col overflow-hidden rounded-2xl border text-left transition ${
            uiStyle === o.id
              ? "border-[var(--fos-focus)] ring-2 ring-[var(--fos-focus)]"
              : "border-[var(--fos-border)] hover:border-[var(--fos-text-muted)]"
          }`}
        >
          <div className="h-24 shrink-0" style={{ background: o.preview }}>
            <div
              className="m-3 h-12 rounded-xl"
              style={{
                background:
                  o.id === "glass" ? "rgba(255,255,255,0.14)" : "#ffffff",
                border: "1px solid rgba(255,255,255,0.25)",
                backdropFilter: o.id === "glass" ? "blur(8px)" : undefined,
              }}
            />
          </div>
          <div className="p-3">
            <p className="font-semibold text-[var(--fos-text)]">{o.name}</p>
            <p className="mt-0.5 text-xs text-[var(--fos-text-muted)]">{o.hint}</p>
          </div>
        </button>
      ))}
    </div>
  );
}

/** Shown once, the first time someone signs in on this device. */
export function FirstLoginStylePicker() {
  const { styleChosen, setUiStyle, uiStyle } = useTheme();

  if (styleChosen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Choose your look"
      className="fixed inset-0 z-[300] flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-lg rounded-3xl border border-[var(--fos-border)] bg-[var(--fos-surface)] p-6 shadow-2xl">
        <h2 className="text-xl font-bold text-[var(--fos-text)]">
          Choose how LINDA looks
        </h2>
        <p className="mt-1 text-sm text-[var(--fos-text-muted)]">
          You can change this any time from your profile menu.
        </p>
        <div className="mt-5">
          <StyleChoices preview />
        </div>
        <button
          type="button"
          onClick={() => setUiStyle(uiStyle)}
          className="mt-5 w-full rounded-xl bg-[var(--fos-primary)] px-4 py-3 text-sm font-semibold text-[var(--fos-on-primary)]"
        >
          Continue
        </button>
      </div>
    </div>
  );
}
