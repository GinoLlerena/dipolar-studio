// The Structure view's camera moves and arcs (src/scene/view.ts), under Node's test runner.
import assert from "node:assert/strict";
import test from "node:test";
import { autoCamera, type Camera, project, type Vec3 } from "../src/scene/projection.ts";
import { arcPath, arcWidth, cameraIn, dolly, keyMove, MIN_DISTANCE, misfitStep, orbit } from "../src/scene/view.ts";

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

test("a dolly moves the planes with the camera, so nothing is clipped", () => {
  for (const factor of [0.5, 0.8, 1.2, 3]) {
    const c = dolly(start, factor);
    const d0 = dist(start.position, start.target);
    near(dist(c.position, c.target), d0 * factor);
    // The near plane follows the camera, but never below the contract's 1e-3 Å.
    near(c.near, Math.max(start.near + d0 * factor - d0, 1e-3));
    near(c.far - start.far, d0 * factor - d0);
    const before = project(start, 640, 480, points).map((p) => p.depth);
    const after = project(c, 640, 480, points).map((p) => p.depth);
    after.forEach((depth, k) => near(depth - (before[k] ?? 0), d0 * factor - d0, 1e-9));
  }
  const closest = dolly(start, 1e-9);
  near(dist(closest.position, closest.target), MIN_DISTANCE);
  assert.ok(closest.near >= 1e-3 && closest.far > closest.near);
});

test("keys orbit and zoom; other keys do nothing", () => {
  assert.notDeepEqual(keyMove(start, "ArrowLeft"), start);
  assert.notDeepEqual(keyMove(start, "+"), start);
  assert.equal(keyMove(start, "a"), null);
  const zoomed = keyMove(start, "+");
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
