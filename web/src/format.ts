// Number formatting for display (docs/panel/ui-design.md §5). Values are rounded only for display,
// never in the data. Pure functions, no imports: tests/format.test.ts runs them under Node.
//
// - The true minus sign (U+2212) and a narrow no-break space between thousands: −2 407.3.
// - An uncertainty is quoted to 1–2 significant figures (two when its leading digit is 1 or 2),
//   and the value is rounded to the same decimal place: 39.60 ± 0.03, or compactly 0.3020(3).

export const MINUS = "−";
const GROUP = " ";
const SUPERSCRIPT = "⁰¹²³⁴⁵⁶⁷⁸⁹";

function grouped(digits: string): string {
  if (digits.length < 4) return digits;
  const head = digits.length % 3 || 3;
  const parts = [digits.slice(0, head)];
  for (let i = head; i < digits.length; i += 3) parts.push(digits.slice(i, i + 3));
  return parts.join(GROUP);
}

function nonFinite(value: number): string {
  if (Number.isNaN(value)) return "—";
  return value > 0 ? "∞" : `${MINUS}∞`;
}

/** `value` to a fixed number of decimals; negative `decimals` round to tens, hundreds, … */
export function fixed(value: number, decimals: number): string {
  if (!Number.isFinite(value)) return nonFinite(value);
  const places = Math.max(decimals, 0);
  const scaled = decimals < 0 ? Math.round(value / 10 ** -decimals) * 10 ** -decimals : value;
  const text = Math.abs(scaled).toFixed(places);
  const [whole = "0", fraction] = text.split(".");
  const isZero = /^[0.]*$/.test(text);
  return (scaled < 0 && !isZero ? MINUS : "") + grouped(whole) + (fraction === undefined ? "" : `.${fraction}`);
}

/** A signed value: "+0.21", "−0.21", and "0.00" for zero at that precision. */
export function signed(value: number, decimals: number): string {
  const text = fixed(value, decimals);
  if (!Number.isFinite(value) || text.startsWith(MINUS) || /^[0. ]*$/.test(text)) return text;
  return `+${text}`;
}

/** The decimal place an uncertainty is quoted to: 1–2 significant figures (two when the
 * rounded uncertainty's leading digit is 1 or 2). Null when `sigma` is not a positive number. */
export function decimalsFor(sigma: number): number | null {
  if (!(sigma > 0) || !Number.isFinite(sigma)) return null;
  const exponent = Math.floor(Math.log10(sigma));
  // The decimal place for `figures` significant figures, and the rounded digits there. Rounding
  // can carry into the next power of ten (0.0996 → 0.100); then one place fewer keeps the count.
  const at = (figures: number): [number, string] => {
    let decimals = figures - 1 - exponent;
    let digits = String(Math.round(sigma * 10 ** decimals));
    if (digits.length > figures) {
      decimals -= 1;
      digits = String(Math.round(sigma * 10 ** decimals));
    }
    return [decimals, digits];
  };
  const [two, digits] = at(2);
  return digits[0] === "1" || digits[0] === "2" ? two : at(1)[0];
}

/** "39.60 ± 0.03"; without a usable uncertainty, the value at `fallbackDecimals`. */
export function withUncertainty(value: number, sigma: number | null | undefined, fallbackDecimals: number): string {
  const decimals = sigma == null ? null : decimalsFor(sigma);
  if (decimals === null || sigma == null || !Number.isFinite(value)) return fixed(value, fallbackDecimals);
  return `${fixed(value, decimals)} ± ${fixed(sigma, decimals)}`;
}

/** "0.3020(3)": the uncertainty in units of the last digit. Falls back to the ± form when the
 * uncertainty is quoted to tens or more (no decimal place to attach it to). */
export function compact(value: number, sigma: number | null | undefined, fallbackDecimals: number): string {
  const decimals = sigma == null ? null : decimalsFor(sigma);
  if (decimals === null || decimals <= 0 || sigma == null || !Number.isFinite(value)) {
    return withUncertainty(value, sigma, fallbackDecimals);
  }
  return `${fixed(value, decimals)}(${Math.round(sigma * 10 ** decimals)})`;
}

/** Two significant figures, in scientific notation outside [10⁻³, 10⁵): "3.2 × 10⁴". */
export function scientific(value: number, figures = 2): string {
  if (!Number.isFinite(value)) return nonFinite(value);
  if (value === 0) return "0";
  const magnitude = Math.abs(value);
  if (magnitude >= 1e-3 && magnitude < 1e5) {
    const exponent = Math.floor(Math.log10(magnitude));
    return fixed(value, Math.max(figures - 1 - exponent, 0));
  }
  const [mantissa = "0", exponent = "0"] = magnitude.toExponential(figures - 1).split("e");
  const power = Number(exponent);
  const sup = [...String(Math.abs(power))].map((d) => SUPERSCRIPT[Number(d)]).join("");
  return `${value < 0 ? MINUS : ""}${mantissa} × 10${power < 0 ? "⁻" : ""}${sup}`;
}

/** A p-value: "< 0.001" below that, otherwise three decimals. */
export function pValue(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return value < 0.001 ? "< 0.001" : value.toFixed(3);
}

/** The smallest and largest finite value, by a loop: spreading a long array into Math.min
 * overflows the call stack (round 39: 2 × 100 000 couplings). Null when there is none. */
export function extent(values: Iterable<number>): [number, number] | null {
  let lo = Number.POSITIVE_INFINITY;
  let hi = Number.NEGATIVE_INFINITY;
  for (const v of values) {
    if (!Number.isFinite(v)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return lo <= hi ? [lo, hi] : null;
}

// The precision each quantity is shown at (ui-design §5).
export const hz = (value: number) => fixed(value, 1);
export const residualHz = (value: number) => signed(value, 2);
export const angstrom = (value: number) => fixed(value, 3);
export const degrees = (value: number) => fixed(value, 2);
export const order = (value: number) => fixed(value, 4);
