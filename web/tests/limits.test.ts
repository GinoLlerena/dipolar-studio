// What the page draws for large projects (src/limits.ts), under Node's test runner.
import assert from "node:assert/strict";
import test from "node:test";
import { MAX_DRAWN, mostRelevant, OVERSCAN, rowWindow } from "../src/limits.ts";

test("the window covers the view plus the overscan, with spacers for the rest", () => {
  assert.deepEqual(rowWindow(10_000, 0, 460, 23), { start: 0, end: 20 + OVERSCAN, before: 0, after: (10_000 - 40) * 23 });
  const w = rowWindow(10_000, 23 * 500, 460, 23);
  assert.deepEqual(w, { start: 480, end: 540, before: 480 * 23, after: (10_000 - 540) * 23 });
  assert.equal(w.before + (w.end - w.start) * 23 + w.after, 10_000 * 23); // the scroll height is kept
  const bottom = rowWindow(10_000, 23 * 9_990, 460, 23);
  assert.equal(bottom.end, 10_000);
  assert.equal(bottom.after, 0);
  assert.deepEqual(rowWindow(0, 0, 460, 23), { start: 0, end: 0, before: 0, after: 0 });
  assert.deepEqual(rowWindow(5, -50, 460, 23), { start: 0, end: 5, before: 0, after: 0 }); // overscrolled
  assert.deepEqual(rowWindow(100, 0, 460, 0), { start: 0, end: 0, before: 0, after: 0 }); // not measured yet
});

test("the most relevant items: everything kept, then the highest scores, in order", () => {
  const items = Array.from({ length: 10 }, (_, i) => ({ id: i, z: [5, 1, 9, 3, 7, 2, 8, 0, 6, 4][i] as number }));
  const picked = mostRelevant(items, (t) => t.z, (t) => t.id === 7, 4);
  assert.deepEqual(picked.map((t) => t.id), [2, 4, 6, 7]); // id 7 kept (z 0), then z 9, 8, 7
  assert.equal(mostRelevant(items, (t) => t.z, () => false, 20).length, 10); // few enough: all
  assert.deepEqual(
    mostRelevant(items, (t) => t.z, () => true, 3).map((t) => t.id),
    items.map((t) => t.id),
  ); // more kept than the limit: the kept ones are never dropped
  const nan = [{ z: Number.NaN }, { z: 1 }, { z: 2 }];
  assert.deepEqual(mostRelevant(nan, (t) => t.z, () => false, 2), [{ z: 1 }, { z: 2 }]); // NaN last
  assert.equal(MAX_DRAWN, 2000);
});
