// The pair orbits the Structure view draws (Phase 2 V1.4, docs/phase2/v1.4-browser.md E-3). Pure
// functions with no imports, so tests/orbits.test.ts runs them under Node.
//
// A fixed-geometry scene gives the group action as `symmetry.images`: for each operation, the
// index in `atoms` of each atom's image. A row's orbit is {sorted(π_g(a), π_g(b))}: the observed
// pair and its symmetry copies, which carry the row's coupling ID and misfit.

/** A row's pair orbit as sorted index pairs, the observed pair first, then the others ascending.
 * Without a group action, the pair alone, as given. */
export function orbitMembers(images: readonly (readonly number[])[] | null, a: number, b: number): [number, number][] {
  if (!images || images.length === 0) return [[a, b]];
  const first: [number, number] = [Math.min(a, b), Math.max(a, b)];
  const key = (p: readonly number[]) => `${p[0]} ${p[1]}`;
  const seen = new Set([key(first)]);
  const others: [number, number][] = [];
  for (const image of images) {
    const x = image[a] as number;
    const y = image[b] as number;
    const pair: [number, number] = [Math.min(x, y), Math.max(x, y)];
    if (!seen.has(key(pair))) {
      seen.add(key(pair));
      others.push(pair);
    }
  }
  others.sort((p, q) => p[0] - q[0] || p[1] - q[1]);
  return [first, ...others];
}

/** One drawn arc: a row's coupling ID, which member of its orbit (0: the observed pair), and its
 * two atoms by index in `atoms`. */
export type OrbitArc = { id: string; copy: number; a: number; b: number };

/** The arcs to draw for `rows` (in the order to fill): every row's observed pair, then the copies
 * of each row in turn while fewer than `max` arcs are drawn. `omitted` counts the copies left out. */
export function orbitArcs(
  rows: readonly { id: string; a: number; b: number }[],
  images: readonly (readonly number[])[] | null,
  max = 2000,
): { arcs: OrbitArc[]; omitted: number } {
  const placed: OrbitArc[][] = [];
  const copies: OrbitArc[][] = [];
  for (const r of rows) {
    const [[a, b], ...rest] = orbitMembers(images, r.a, r.b) as [[number, number], ...[number, number][]];
    placed.push([{ id: r.id, copy: 0, a, b }]);
    copies.push(rest.map(([x, y], j) => ({ id: r.id, copy: j + 1, a: x, b: y })));
  }
  let budget = max - rows.length;
  let omitted = 0;
  copies.forEach((list, k) => {
    for (const arc of list) {
      if (budget > 0) {
        (placed[k] as OrbitArc[]).push(arc);
        budget -= 1;
      } else omitted += 1;
    }
  });
  return { arcs: placed.flat(), omitted };
}
