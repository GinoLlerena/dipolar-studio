// The Structure view's camera moves and arcs (src/scene/view.ts), under Node's test runner.
import assert from "node:assert/strict";
import test from "node:test";
import { autoCamera, type Camera, project, type Vec3 } from "../src/scene/projection.ts";
import {
  arcPath,
  arcWidth,
  CameraCommits,
  cameraIn,
  dolly,
  guarded,
  keyMove,
  MIN_DISTANCE,
  misfitStep,
  orbit,
  radiusAbout,
  withinLimits,
} from "../src/scene/view.ts";

const dist = (a: Vec3, b: Vec3) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const near = (a: number, b: number, tol = 1e-9) => assert.ok(Math.abs(a - b) <= tol, `${a} != ${b}`);

const points: Vec3[] = [
  [1.2, 0.3, -0.4],
  [-0.8, 1.1, 0.6],
  [0.1, -1.4, 0.9],
  [2.4, 0.2, 1.3],
];
const start = autoCamera(points, 640, 480);

test("an orbit keeps the distance, the planes and an up vector square to the view", () => {
  let c: Camera = start;
  for (const [yaw, pitch] of [[30, 0], [0, 50], [-75, 80], [10, -170], [400, 33]] as const) {
    c = orbit(c, yaw, pitch);
    near(dist(c.position, c.target), dist(start.position, start.target));
    assert.equal(c.near, start.near);
    assert.equal(c.far, start.far);
    const forward: Vec3 = [c.target[0] - c.position[0], c.target[1] - c.position[1], c.target[2] - c.position[2]];
    near(dot(forward, c.up), 0, 1e-9 * dist(c.position, c.target));
  }
  // Passing over the pole never makes the up vector parallel to the view (no gimbal lock).
  const over = orbit(start, 0, 90);
  const projected = project(over, 640, 480, points);
  assert.ok(projected.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y)));
});

test("orbits invert, and a full turn comes back", () => {
  const there = orbit(orbit(start, 37, 0), -37, 0);
  for (let k = 0; k < 3; k++) near(there.position[k] ?? 0, start.position[k] ?? 0, 1e-9);
  const round = orbit(start, 360, 0);
  for (let k = 0; k < 3; k++) near(round.position[k] ?? 0, start.position[k] ?? 0, 1e-9);
});

test("an orbit keeps every point in view: the depths stay within the planes", () => {
  for (const [yaw, pitch] of [[90, 0], [0, 90], [45, 45], [180, 0]] as const) {
    const projected = project(orbit(start, yaw, pitch), 640, 480, points);
    assert.ok(projected.every((p) => p.visible), `${yaw}/${pitch}`);
  }
});

const radius = radiusAbout(points, start.target);

test("a dolly keeps every point inside the planes, and zooming in and back out restores them (round 41)", () => {
  for (const factor of [0.5, 0.8, 1.2, 3]) {
    const c = dolly(start, factor, radius);
    const d0 = dist(start.position, start.target);
    near(dist(c.position, c.target), d0 * factor);
    assert.ok(project(c, 640, 480, points).every((p) => p.depth >= c.near && p.depth <= c.far), `${factor}`);
  }
  // Far enough in that the near plane clamps, then back out: the planes come back exactly as
  // autoCamera set them, and every atom is visible again.
  let c: Camera = start;
  for (let k = 0; k < 12; k++) c = dolly(c, 1 / 1.2, radius);
  assert.equal(c.near, 1e-3);
  for (let k = 0; k < 12; k++) c = dolly(c, 1.2, radius);
  near(c.near, start.near, 1e-9);
  near(c.far, start.far, 1e-9);
  assert.ok(project(c, 640, 480, points).every((p) => p.visible));
  const closest = dolly(start, 1e-9, radius);
  near(dist(closest.position, closest.target), MIN_DISTANCE);
  assert.ok(closest.near >= 1e-3 && closest.far > closest.near);
});

test("a move the server would refuse leaves the camera unchanged (round 41)", () => {
  const huge: Camera = { ...start, far: 1_000_000 };
  assert.ok(withinLimits(huge));
  const out = keyMove(huge, "-", 999_999);
  assert.deepEqual(out, huge); // zooming out would push far past 1e6 Å
  assert.ok(!withinLimits({ ...start, near: 0 }));
  assert.ok(!withinLimits({ ...start, fov_deg: 175 }));
  assert.ok(!withinLimits({ ...start, up: [0, 0, -1] })); // parallel to the view
  assert.deepEqual(guarded(start, { ...start, near: Number.NaN }), start);
});

/** Timers driven by hand. */
function fakeTimers() {
  let next = 0;
  const due = new Map<number, () => void>();
  return {
    timers: {
      set: (fn: () => void) => {
        next += 1;
        due.set(next, fn);
        return next;
      },
      clear: (handle: unknown) => {
        due.delete(handle as number);
      },
    },
    runAll: () => {
      for (const [k, fn] of [...due]) {
        due.delete(k);
        fn();
      }
    },
    pending: () => due.size,
  };
}

test("a delayed camera commit is dropped when a newer revision arrives first (round 41)", () => {
  const clock = fakeTimers();
  const sent: [Camera | null, number | null][] = [];
  const commits = new CameraCommits(3, (c, r) => sent.push([c, r]), clock.timers);
  const moved = orbit(start, 15, 0);
  commits.later(moved, 3, 400);
  commits.observe(4); // another client moved the camera meanwhile: theirs wins
  assert.equal(clock.pending(), 0); // the timer is cancelled at once
  assert.ok(!commits.waiting);
  clock.runAll();
  assert.deepEqual(sent, []);
  // Moved from the current view, the commit goes out once, after the delay, naming its revision.
  commits.later(moved, 4, 400);
  commits.observe(4);
  clock.runAll();
  assert.deepEqual(sent, [[moved, 4]]);
});

test("a camera moved from a view older than any response has shown is never sent (round 42)", () => {
  const clock = fakeTimers();
  const sent: [Camera | null, number | null][] = [];
  const commits = new CameraCommits(5, (c, r) => sent.push([c, r]), clock.timers);
  // The view read answered at revision 6 while the scene (and the camera shown) is still at 5.
  commits.observe(6);
  commits.later(orbit(start, 15, 0), 5, 400);
  assert.equal(clock.pending(), 0);
  commits.now(orbit(start, 30, 0), 5); // a drag that ends on the old scene
  clock.runAll();
  assert.deepEqual(sent, []);
  commits.observe(5); // an older report changes nothing
  commits.later(orbit(start, 15, 0), 6, 400);
  clock.runAll();
  assert.equal(sent.length, 1);
  assert.equal(sent[0]?.[1], 6);
});

test("fit to view supersedes a pending key commit, and a later key restarts the delay (round 41)", () => {
  const clock = fakeTimers();
  const sent: [Camera | null, number | null][] = [];
  const commits = new CameraCommits(1, (c, r) => sent.push([c, r]), clock.timers);
  commits.later(orbit(start, 15, 0), 1, 400);
  commits.now(null, null);
  clock.runAll();
  assert.deepEqual(sent, [[null, null]]);
  const a = orbit(start, 15, 0);
  const b = orbit(a, 15, 0);
  commits.later(a, 1, 400);
  commits.later(b, 1, 400);
  assert.equal(clock.pending(), 1);
  clock.runAll();
  assert.deepEqual(sent, [
    [null, null],
    [b, 1],
  ]);
});

test("keys orbit and zoom; other keys do nothing", () => {
  assert.notDeepEqual(keyMove(start, "ArrowLeft", radius), start);
  assert.notDeepEqual(keyMove(start, "+", radius), start);
  assert.equal(keyMove(start, "a", radius), null);
  const zoomed = keyMove(start, "+", radius);
  assert.ok(zoomed && dist(zoomed.position, zoomed.target) < dist(start.position, start.target));
});

test("the misfit ramp and arc widths grow with |residual|/σ", () => {
  assert.deepEqual([0, 0.49, 0.5, 1, 1.5, 2, 2.99, 3, -4, Number.NaN].map(misfitStep), [0, 0, 1, 2, 3, 4, 4, 5, 5, 5]);
  const widths = [0, 1, 2, 3, 4, 5].map(arcWidth);
  assert.ok(widths.every((w, k) => k === 0 || w > (widths[k - 1] ?? 0)));
  assert.equal(arcWidth(99), arcWidth(5));
});

test("an arc runs from one spin to the other and bows sideways", () => {
  assert.equal(arcPath({ x: 0, y: 0 }, { x: 100, y: 0 }, 0.2), "M0,0 Q50,20 100,0");
  assert.equal(arcPath({ x: 0, y: 0 }, { x: 0, y: 0 }), "M0,0 Q0,0 0,0");
});

test("the committed camera is the moved camera, in the contract's units", () => {
  const c = orbit(start, 20, 10);
  const wire = cameraIn(c);
  assert.deepEqual(wire.position.xyz, [...c.position]);
  assert.equal(wire.position.unit, "Å");
  assert.equal(wire.fov.unit, "deg");
  assert.equal(wire.near.value, c.near);
});
