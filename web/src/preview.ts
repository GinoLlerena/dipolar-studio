// Live preview (M3 step 3): the φ slider and the χ²(φ) landscape. Pure functions and a small
// scheduler with type-only imports, so tests/preview.test.ts runs them under Node.
//
// Dragging the slider asks for fit.preview at every position, faster than the server answers.
// `LatestOnly` keeps one request in flight; while it runs, only the newest position waits, and it
// is sent when the answer arrives. So the page never queues stale positions behind each other,
// an answer is never older than one shown before it (D11), and the last position is always
// previewed.

/** Round-trip times kept for the p95 (the preview target is measured in M3 step 4). */
export const KEPT_TIMINGS = 200;

type Clock = () => number;

export class LatestOnly<Q, R> {
  private running = false;
  private waitingFor: { query: Q } | null = null;
  private readonly request: (query: Q) => Promise<R | null>;
  private readonly show: (query: Q, result: R) => void;
  private readonly clock: Clock;
  /** Milliseconds per answered request, the newest last. */
  readonly timings: number[] = [];

  // No parameter properties: Node's type stripping (tests/preview.test.ts) does not support them.
  constructor(request: (query: Q) => Promise<R | null>, show: (query: Q, result: R) => void, clock: Clock) {
    this.request = request;
    this.show = show;
    this.clock = clock;
  }

  /** Previews `query` as soon as the request in flight (if any) has answered. */
  ask(query: Q): void {
    if (this.running) {
      this.waitingFor = { query };
      return;
    }
    void this.send(query);
  }

  /** Drops a waiting query (the pane is closing, or the page moved on). */
  cancel(): void {
    this.waitingFor = null;
  }

  get busy(): boolean {
    return this.running;
  }

  private async send(query: Q): Promise<void> {
    this.running = true;
    const started = this.clock();
    let result: R | null = null;
    try {
      result = await this.request(query);
    } finally {
      this.running = false;
    }
    if (result !== null) {
      this.timings.push(this.clock() - started);
      if (this.timings.length > KEPT_TIMINGS) this.timings.shift();
      // A newer position waits: its answer comes next, so this one may still be shown (it is the
      // newest answer there is), and the slider never looks frozen during a long drag.
      this.show(query, result);
    }
    const next = this.waitingFor;
    this.waitingFor = null;
    if (next) void this.send(next.query);
  }
}

/** The 95th percentile of `samples` (nearest rank), or null when there are none. */
export function p95(samples: readonly number[]): number | null {
  if (samples.length === 0) return null;
  const sorted = [...samples].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.ceil(0.95 * sorted.length) - 1)] ?? null;
}

/** `value` within [lo, hi], rounded to `step` (the slider's resolution). */
export function snap(value: number, lo: number, hi: number, step: number): number {
  const clamped = Math.min(Math.max(value, lo), hi);
  const n = Math.round((clamped - lo) / step);
  return Math.min(hi, Number((lo + n * step).toFixed(10)));
}

/** The index of the sample nearest to `value` (the first of two equally near). */
export function nearest(phi: readonly number[], value: number): number {
  let best = 0;
  for (let i = 1; i < phi.length; i++) {
    if (Math.abs((phi[i] ?? 0) - value) < Math.abs((phi[best] ?? 0) - value)) best = i;
  }
  return best;
}

/** The lowest sampled χ² and where it is, or null when no sample could be evaluated. */
export function lowest(phi: readonly number[], chi2: readonly (number | null)[]): { phi: number; chi2: number } | null {
  let found: { phi: number; chi2: number } | null = null;
  chi2.forEach((c, i) => {
    if (c !== null && (found === null || c < found.chi2)) found = { phi: phi[i] ?? 0, chi2: c };
  });
  return found;
}

/** The landscape's vertical axis is log₁₀ χ²: χ² spans decades between the minimum and the far
 * torsions, and the minimum is what matters. A χ² of zero (noiseless data) is drawn at the floor;
 * null only when no sample could be evaluated. */
export function logRange(chi2: readonly (number | null)[]): { lo: number; hi: number } | null {
  const positive = chi2.filter((c): c is number => c !== null && c > 0);
  if (positive.length === 0) {
    // Only zeros (an exact fit everywhere, round 47) still draw, at the floor; only gaps do not.
    return chi2.some((c) => c !== null) ? { lo: 0, hi: 1 } : null;
  }
  let lo = Math.floor(Math.log10(Math.min(...positive)));
  let hi = Math.ceil(Math.log10(Math.max(...positive)));
  if (hi <= lo) hi = lo + 1;
  return { lo, hi };
}

/** An SVG path through the samples, with a gap wherever χ² could not be evaluated. */
export function landscapePath(
  phi: readonly number[],
  chi2: readonly (number | null)[],
  x: (phi: number) => number,
  y: (chi2: number) => number,
): string {
  const f = (v: number) => (Math.round(v * 100) / 100).toString();
  let path = "";
  let pen = false;
  chi2.forEach((c, i) => {
    if (c === null) {
      pen = false;
      return;
    }
    path += `${pen ? "L" : path === "" ? "M" : " M"}${f(x(phi[i] ?? 0))},${f(y(c))}`;
    pen = true;
  });
  return path;
}

/** The φ field's text: plain ASCII, so that it can be edited and parsed again (round 47: the
 * typographic minus of `fixed` is not a number to `Number`). */
export function inputText(phi: number): string {
  return phi.toFixed(1);
}

/** A typed angle, accepting the typographic minus and a leading plus; null when not a number. */
export function parseAngle(text: string): number | null {
  const plain = text.trim().replace(/^[\u2212\u2013]/, "-");
  if (!/^[+-]?(\d+\.?\d*|\.\d+)$/.test(plain)) return null;
  const value = Number(plain);
  return Number.isFinite(value) ? value : null;
}
