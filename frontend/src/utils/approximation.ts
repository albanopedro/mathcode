/**
 * The decimal form of a result (Phase 11, ADR 0018): the API sends it with 15
 * significant digits ("0.523598775598299", "-2; 3.5", "1.5e+20"); here each
 * number is rounded to the digits chosen and written with a decimal comma.
 */
export const MIN_DIGITS = 2;
export const MAX_DIGITS = 15;
export const DEFAULT_DIGITS = 6;

const NUMBER = /-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/gi;
const SUPERSCRIPTS: Record<string, string> = {
  "0": "⁰",
  "1": "¹",
  "2": "²",
  "3": "³",
  "4": "⁴",
  "5": "⁵",
  "6": "⁶",
  "7": "⁷",
  "8": "⁸",
  "9": "⁹",
  "-": "⁻",
};

function roundOne(token: string, digits: number): string {
  const value = Number(token);
  if (!Number.isFinite(value)) {
    return token;
  }
  const [mantissa, exponent] = value.toPrecision(digits).split("e");
  // Trailing zeros say nothing: 0.375000 is 0.375.
  const trimmed = mantissa!.includes(".") ? mantissa!.replace(/\.?0+$/, "") : mantissa!;
  const comma = trimmed.replace(".", ",");
  if (exponent === undefined) {
    return comma;
  }
  const power = String(Number(exponent))
    .split("")
    .map((ch) => SUPERSCRIPTS[ch] ?? ch)
    .join("");
  return `${comma}·10${power}`;
}

export function formatApprox(approx: string, digits: number): string {
  const safe = Math.min(MAX_DIGITS, Math.max(MIN_DIGITS, Math.round(digits)));
  // Number separators of lists ("; ") and points (", ") stay as they are.
  return approx.replace(NUMBER, (token) => roundOne(token, safe));
}

// -- the preference, kept in this browser -----------------------------------------------------

export const DISPLAY_KEY = "mathcode.display.v1";

export interface DisplayPreference {
  mode: "exact" | "approx";
  digits: number;
}

export const DEFAULT_DISPLAY: DisplayPreference = { mode: "exact", digits: DEFAULT_DIGITS };

export function loadDisplay(): DisplayPreference {
  try {
    const raw = window.localStorage.getItem(DISPLAY_KEY);
    const parsed = raw ? (JSON.parse(raw) as Partial<DisplayPreference>) : {};
    const mode = parsed.mode === "approx" ? "approx" : "exact";
    const digits =
      typeof parsed.digits === "number" && parsed.digits >= MIN_DIGITS && parsed.digits <= MAX_DIGITS
        ? Math.round(parsed.digits)
        : DEFAULT_DIGITS;
    return { mode, digits };
  } catch {
    return DEFAULT_DISPLAY;
  }
}

export function saveDisplay(preference: DisplayPreference): void {
  try {
    window.localStorage.setItem(DISPLAY_KEY, JSON.stringify(preference));
  } catch {
    // Blocked storage: the choice lasts until the page is closed.
  }
}
