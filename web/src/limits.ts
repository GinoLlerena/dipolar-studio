// What the page draws for large projects (M3 step 4b). Pure functions with no imports, so
// tests/limits.test.ts runs them under Node.
//
// A project may hold up to 100 000 couplings. Tables then render only the rows in view (windowed),
// and the plots and the Structure view draw at most a fixed number of couplings: the ones that
// matter most (the largest misfits, and everything selected or highlighted), and say so.

/** Tables longer than this are windowed; shorter ones render every row (as before). */
export const WINDOW_FROM = 400;
/** Rows rendered beyond each edge of the view, so a scroll never shows an empty band. */
export const OVERSCAN = 20;

export type RowWindow = { start: number; end: number; before: number; after: number };

/** The rows [start, end) to render for a scroll position, with the heights (px) of the spacers
 * that stand in for the rows above and below. A position beyond the rows' end (a scroll position
 * left from a longer table, round 51) shows the last rows, never an empty window. */
export function rowWindow(count: number, top: number, height: number, row: number, overscan = OVERSCAN): RowWindow {
  if (count <= 0 || !(row > 0)) return { start: 0, end: 0, before: 0, after: 0 };
  const view = Math.max(height, 0);
  const at = Math.min(Math.max(top, 0), Math.max(0, count * row - view));
  const first = Math.floor(at / row);
  const start = Math.min(count - 1, Math.max(0, first - overscan));
  const end = Math.min(count, Math.max(start + 1, Math.ceil((at + view) / row) + overscan));
  return { start, end, before: start * row, after: (count - end) * row };
}

/** Couplings drawn at most in the observed-vs-calculated plot and in the Structure view. */
export const MAX_DRAWN = 2000;

/** At most `max` items: every item `keep` names (selected, highlighted), then the highest
 * `score`s (ties by position); in their original order. All of them when there are few enough. */
export function mostRelevant<T>(items: readonly T[], score: (item: T) => number, keep: (item: T) => boolean, max = MAX_DRAWN): T[] {
  if (items.length <= max) return [...items];
  const chosen = new Set<number>();
  items.forEach((item, i) => {
    if (keep(item)) chosen.add(i);
  });
  const ranked = items
    .map((item, i) => ({ i, s: score(item) }))
    .filter(({ i }) => !chosen.has(i))
    .sort((a, b) => (b.s === a.s ? a.i - b.i : Number.isNaN(b.s) ? -1 : Number.isNaN(a.s) ? 1 : b.s - a.s));
  for (const { i } of ranked) {
    if (chosen.size >= max) break;
    chosen.add(i);
  }
  return [...chosen].sort((a, b) => a - b).map((i) => items[i] as T);
}
