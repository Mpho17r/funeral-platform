/**
 * Turns a business's chosen colours into the platform's colours.
 *
 *  - Primary   -> sidebar, buttons and other solid surfaces
 *  - Secondary -> accents: the active menu marker, highlights, focus rings
 *
 * Businesses created before colours were editable were saved with black and
 * slate as placeholders. Those count as "not chosen", so they keep the LINDA
 * look instead of turning black.
 */

const LEGACY_PRIMARY = new Set(["#000000", "#000", "#0f172a"]);
const LEGACY_SECONDARY = new Set(["#64748b"]);
const STYLE_ID = "linda-brand-theme";

export function normaliseHex(value: string | null | undefined): string | null {
  const text = (value ?? "").trim().toLowerCase();
  const short = /^#([0-9a-f]{3})$/.exec(text);

  if (short) {
    return `#${short[1].split("").map((c) => c + c).join("")}`;
  }

  return /^#[0-9a-f]{6}$/.test(text) ? text : null;
}

function rgb(hex: string): [number, number, number] {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as [
    number,
    number,
    number,
  ];
}

/** 0 (black) to 1 (white), as the eye sees it. */
export function luminance(hex: string): number {
  const [r, g, b] = rgb(hex).map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });

  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Mix with black (amount > 0) or white (amount < 0). */
function shade(hex: string, amount: number): string {
  const target = amount >= 0 ? 0 : 255;
  const a = Math.abs(amount);
  const out = rgb(hex).map((v) => Math.round(v + (target - v) * a));

  return `#${out.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

/**
 * The sidebar puts white text on the primary colour, so a very light
 * primary would make the menu unreadable.
 */
export function primaryIsTooLight(hex: string | null | undefined): boolean {
  const colour = normaliseHex(hex);

  return !!colour && luminance(colour) > 0.45;
}

export function buildBrandCss(
  primaryInput: string | null | undefined,
  secondaryInput: string | null | undefined,
): string {
  let primary = normaliseHex(primaryInput);
  let secondary = normaliseHex(secondaryInput);

  if (!primary || LEGACY_PRIMARY.has(primary) || primaryIsTooLight(primary)) {
    primary = null;
  }

  if (!secondary || LEGACY_SECONDARY.has(secondary)) {
    secondary = null;
  }

  const light: string[] = [];
  const dark: string[] = [];

  if (primary) {
    light.push(
      `--linda-navy:${primary}`,
      `--fos-primary:${primary}`,
      `--fos-primary-hover:${shade(primary, 0.2)}`,
      `--fos-on-primary:#ffffff`,
    );
    // Dark mode keeps its own light buttons; only the sidebar follows the brand.
    dark.push(`--linda-navy:${shade(primary, 0.25)}`);
  }

  if (secondary) {
    light.push(
      `--linda-gold:${secondary}`,
      `--linda-gold-text:${shade(secondary, 0.4)}`,
      `--fos-focus:${shade(secondary, 0.15)}`,
    );
    dark.push(
      `--linda-gold:${secondary}`,
      `--linda-gold-text:${secondary}`,
      `--fos-focus:${secondary}`,
    );
  }

  if (!light.length) {
    return "";
  }

  return `:root{${light.join(";")}}html.dark{${dark.join(";")}}`;
}

export function applyBrandTheme(
  primary: string | null | undefined,
  secondary: string | null | undefined,
): void {
  if (typeof document === "undefined") {
    return;
  }

  const css = buildBrandCss(primary, secondary);
  let element = document.getElementById(STYLE_ID);

  if (!css) {
    element?.remove();
    return;
  }

  if (!element) {
    element = document.createElement("style");
    element.id = STYLE_ID;
    document.head.appendChild(element);
  }

  element.textContent = css;
}

export function clearBrandTheme(): void {
  if (typeof document !== "undefined") {
    document.getElementById(STYLE_ID)?.remove();
  }
}
