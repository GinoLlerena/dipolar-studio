// The Structure view's pair orbits (src/scene/orbits.ts; docs/phase2/v1.4-browser.md E-3): every
// member of a row's orbit is drawn from the scene's group action, within the drawing limit.
import assert from "node:assert/strict";
import test from "node:test";
import { orbitArcs, orbitMembers } from "../src/scene/orbits.ts";

// 1,4-dichlorobenzene's protons as atoms 0–3 (H2, H3, H5, H6) under D2h: its eight operations act
// on them as the identity, the swaps across x and y, and the inversion (each twice: σh fixes them).
const ID = [0, 1, 2, 3];
const MX = [3, 2, 1, 0]; // across the xz plane: H2↔H6, H3↔H5
const MY = [1, 0, 3, 2]; // across the yz plane: H2↔H3, H5↔H6
const INV = [2, 3, 0, 1]; // H2↔H5, H3↔H6
const D2H = [ID, MX, MY, INV, ID, MX, MY, INV];

test("an orbit is its sorted pairs, the observed one first", () => {
  assert.deepEqual(orbitMembers(D2H, 0, 1), [
    [0, 1],
    [2, 3],
  ]);
  assert.deepEqual(orbitMembers(D2H, 3, 0), [
    [0, 3],
    [1, 2],
  ]);
  assert.deepEqual(orbitMembers(D2H, 2, 0), [
    [0, 2],
    [1, 3],
  ]);
  assert.deepEqual(orbitMembers([ID], 2, 1), [[1, 2]]); // C1: the pair alone
});

test("every row's observed pair is drawn, then copies in row order up to the limit", () => {
  const rows = [
    { id: "cpl_1", a: 0, b: 1 },
    { id: "cpl_2", a: 0, b: 3 },
    { id: "cpl_3", a: 0, b: 2 },
  ];
  const all = orbitArcs(rows, D2H);
  assert.equal(all.omitted, 0);
  assert.deepEqual(
    all.arcs.map((x) => [x.id, x.copy, x.a, x.b]),
    [
      ["cpl_1", 0, 0, 1],
      ["cpl_1", 1, 2, 3],
      ["cpl_2", 0, 0, 3],
      ["cpl_2", 1, 1, 2],
      ["cpl_3", 0, 0, 2],
      ["cpl_3", 1, 1, 3],
    ],
  );
  const limited = orbitArcs(rows, D2H, 4);
  assert.equal(limited.arcs.length, 4);
  assert.equal(limited.omitted, 2);
  assert.deepEqual(limited.arcs.filter((x) => x.copy === 0).map((x) => x.id), ["cpl_1", "cpl_2", "cpl_3"]);
  // The observed pairs are never dropped, even below the limit.
  assert.deepEqual(orbitArcs(rows, D2H, 2).arcs.map((x) => x.copy), [0, 0, 0]);
});

test("without a group action each row is its own pair", () => {
  const out = orbitArcs([{ id: "cpl_1", a: 4, b: 2 }], null);
  assert.deepEqual(out, { arcs: [{ id: "cpl_1", copy: 0, a: 4, b: 2 }], omitted: 0 });
});

test("round 79: the copies of a selected or highlighted row are drawn whatever the budget", () => {
  const rows = [
    { id: "cpl_1", a: 0, b: 1 },
    { id: "cpl_2", a: 0, b: 3 },
    { id: "cpl_3", a: 0, b: 2 },
  ];
  const out = orbitArcs(rows, D2H, 3, new Set(["cpl_3"]));
  assert.deepEqual(out.arcs.map((x) => [x.id, x.copy]), [
    ["cpl_1", 0],
    ["cpl_2", 0],
    ["cpl_3", 0],
    ["cpl_3", 1],
  ]);
  assert.equal(out.omitted, 2);
});

test("round 80: the copies of selected and highlighted rows have their own bound", () => {
  // 2000 kept rows with 24 members each would be 48 000 arcs: at most 2 × max are drawn.
  const images = Array.from({ length: 24 }, (_, g) => Array.from({ length: 48 }, (_, i) => (i + 2 * g) % 48));
  const rows = Array.from({ length: 2000 }, (_, k) => ({ id: `cpl_${k}`, a: 0, b: 1 + (k % 40) }));
  const keep = new Set(rows.map((r) => r.id));
  const out = orbitArcs(rows, images, 2000, keep);
  assert.ok(out.arcs.length <= 4000, `${out.arcs.length} arcs`);
  assert.ok(out.omitted > 0);
  // The first kept row's orbit is drawn whole.
  const first = out.arcs.filter((x) => x.id === "cpl_0").length;
  assert.equal(first, orbitArcs([rows[0]!], images).arcs.length);
});
