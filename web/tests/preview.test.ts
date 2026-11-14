// Live preview helpers (src/preview.ts), under Node's test runner.
import assert from "node:assert/strict";
import test from "node:test";
import {
  boundsCurrent,
  inputText,
  KEPT_TIMINGS,
  LatestOnly,
  landscapePath,
  logRange,
  lowest,
  nearest,
  p95,
  parseAngle,
  snap,
  startAt,
} from "../src/preview.ts";

/** A fetch whose answers the test releases by hand. */
function manual() {
  const calls: { query: number; resolve: (r: string | null) => void }[] = [];
  const fetch = (query: number) => new Promise<string | null>((resolve) => calls.push({ query, resolve }));
  return { calls, fetch };
}
const tick = () => new Promise((r) => setTimeout(r, 0));

test("one request in flight; only the newest position waits, and it is sent next", async () => {
  const { calls, fetch } = manual();
  const shown: [number, string][] = [];
  let t = 0;
  const live = new LatestOnly(fetch, (q: number, r: string) => shown.push([q, r]), () => t);
  live.ask(10);
  live.ask(11);
  live.ask(12); // replaces 11
  assert.deepEqual(calls.map((c) => c.query), [10]);
  t = 25;
  calls[0]?.resolve("a");
  await tick();
  assert.deepEqual(shown, [[10, "a"]]);
  assert.deepEqual(calls.map((c) => c.query), [10, 12]);
  t = 40;
  calls[1]?.resolve("c");
  await tick();
  assert.deepEqual(shown, [[10, "a"], [12, "c"]]);
  assert.deepEqual(live.timings, [25, 15]);
  assert.equal(live.busy, false);
});

test("a failed request shows nothing and still sends the waiting position", async () => {
  const { calls, fetch } = manual();
  const shown: number[] = [];
  const live = new LatestOnly(fetch, (q: number) => shown.push(q), () => 0);
  live.ask(1);
  live.ask(2);
  calls[0]?.resolve(null);
  await tick();
  assert.deepEqual(calls.map((c) => c.query), [1, 2]);
  calls[1]?.resolve("ok");
  await tick();
  assert.deepEqual(shown, [2]);
  assert.equal(live.timings.length, 1);
});

test("cancel drops the waiting position", async () => {
  const { calls, fetch } = manual();
  const live = new LatestOnly(fetch, () => {}, () => 0);
  live.ask(1);
  live.ask(2);
  live.cancel();
  calls[0]?.resolve("x");
  await tick();
  assert.equal(calls.length, 1);
});

test("timings are bounded", async () => {
  const live = new LatestOnly(async (q: number) => String(q), () => {}, () => 0);
  for (let i = 0; i < KEPT_TIMINGS + 5; i++) {
    live.ask(i);
    await tick();
  }
  assert.equal(live.timings.length, KEPT_TIMINGS);
});

test("p95 by nearest rank", () => {
  assert.equal(p95([]), null);
  assert.equal(p95([7]), 7);
  assert.equal(p95(Array.from({ length: 100 }, (_, i) => i + 1)), 95);
  assert.equal(p95([5, 1, 3]), 5);
});

test("snap clamps to the domain and rounds to the step", () => {
  assert.equal(snap(37.04, 0, 90, 0.1), 37);
  assert.equal(snap(37.06, 0, 90, 0.1), 37.1);
  assert.equal(snap(-3, 0, 90, 0.1), 0);
  assert.equal(snap(95, 0, 90, 0.1), 90);
  assert.equal(snap(89.99, 0, 90, 0.25), 90);
});

test("nearest sample, lowest sample, gaps skipped", () => {
  const phi = [0, 10, 20, 30];
  assert.equal(nearest(phi, 14), 1);
  assert.equal(nearest(phi, 15), 1); // a tie goes to the first
  assert.equal(nearest(phi, 99), 3);
  assert.deepEqual(lowest(phi, [5, null, 2, 3]), { phi: 20, chi2: 2 });
  assert.equal(lowest(phi, [null, null, null, null]), null);
});

test("the log axis spans whole decades; zero χ² sits at the floor", () => {
  assert.deepEqual(logRange([12, 3400, null]), { lo: 1, hi: 4 });
  assert.deepEqual(logRange([100, 100]), { lo: 2, hi: 3 });
  assert.deepEqual(logRange([0, 50]), { lo: 1, hi: 2 });
  assert.deepEqual(logRange([0, null]), { lo: 0, hi: 1 });
});

test("the landscape path breaks where χ² could not be evaluated", () => {
  const path = landscapePath([0, 1, 2, 3, 4], [1, 2, null, 4, 5], (p) => p * 10, (c) => c);
  assert.equal(path, "M0,1L10,2 M30,4L40,5");
  assert.equal(landscapePath([0], [null], (p) => p, (c) => c), "");
});

test("only zeros still draw, at the floor; only gaps do not (round 47)", () => {
  assert.deepEqual(logRange([0, 0, 0]), { lo: 0, hi: 1 });
  assert.equal(logRange([null, null]), null);
});

test("the φ field: ASCII text that parses back, the typographic minus accepted (round 47)", () => {
  assert.equal(inputText(-25), "-25.0");
  assert.equal(parseAngle(inputText(-25.1)), -25.1);
  assert.equal(parseAngle("−25.1"), -25.1); // U+2212, as `fixed` writes it
  assert.equal(parseAngle(" +37 "), 37);
  assert.equal(parseAngle(".5"), 0.5);
  for (const bad of ["", "abc", "1e3", "Infinity", "1_0", "١٢", "--1", "1.2.3"]) assert.equal(parseAngle(bad), null, bad);
});

test("the preview starts only once the domain is the current science's, in either order (round 48)", () => {
  const land = { science_revision: 5, phi: [0, 60, 120, 180], chi2: [9, 4, 1, 7] };
  const base = { current: null, fitted: null, landscape: land, projectRevision: 5, viewRevision: 5 };
  assert.equal(startAt(base), 120); // the landscape's lowest sample
  assert.equal(startAt({ ...base, fitted: 121.5 }), 121.5); // the fit first
  // The view (or the landscape) is newer than the project's domain: wait for project.describe.
  assert.equal(startAt({ ...base, projectRevision: 4 }), null);
  assert.equal(startAt({ ...base, projectRevision: null }), null);
  // The project is newer than the view: wait for the view.
  assert.equal(startAt({ ...base, viewRevision: 4 }), null);
  // A landscape of an older science is not a start.
  assert.equal(startAt({ ...base, landscape: { ...land, science_revision: 4 } }), null);
  assert.equal(startAt({ ...base, current: 30 }), null); // already started
  assert.equal(boundsCurrent(3, 3), true);
  assert.equal(boundsCurrent(3, 4), false);
});
