// The Structure view's geometry (M3 step 2): camera moves and misfit arcs. Pure functions with
// type-only imports, so tests/view.test.ts runs them under Node.
//
// The page draws the scene from `render.scene`: 3D positions and the shared camera, projected
// here by projection.ts (pixel-identical to the server's renderer). A drag or a key moves a local
// copy of the camera at once; the page commits it with `view.set_camera` when the gesture ends,
// so every client and the robot see the same view, and there is one journal entry per gesture.

import type { CameraIn, SceneCamera } from "../generated/contract";
import type { Camera, Vec3 } from "./projection";

const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const add = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const scale = (a: Vec3, k: number): Vec3 => [a[0] * k, a[1] * k, a[2] * k];
const dot = (a: Vec3, b: Vec3): number => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
const norm = (a: Vec3): number => Math.sqrt(dot(a, a));
const unit = (a: Vec3): Vec3 => scale(a, 1 / norm(a));

/** `v` rotated by `degrees` about the unit axis `k` (Rodrigues). */
function rotate(v: Vec3, k: Vec3, degrees: number): Vec3 {
  const t = (degrees * Math.PI) / 180;
  const c = Math.cos(t);
  const s = Math.sin(t);
  return add(add(scale(v, c), scale(cross(k, v), s)), scale(k, dot(k, v) * (1 - c)));
}

/** The camera's orthonormal frame: viewing direction, screen right and screen up. */
function frame(camera: Camera): { forward: Vec3; side: Vec3; up: Vec3 } {
  const forward = unit(sub(camera.target, camera.position));
  const side = unit(cross(forward, camera.up));
  return { forward, side, up: cross(side, forward) };
}

/** Orbits the camera about its target: `yaw` about the screen's up axis, `pitch` about its right
 * axis (degrees). The distance to the target and the depth planes are unchanged, and the up
 * vector turns with the camera, so it never becomes parallel to the view (no gimbal lock). */
export function orbit(camera: Camera, yaw: number, pitch: number): Camera {
  const { side, up } = frame(camera);
  let offset = sub(camera.position, camera.target);
  let newUp = up;
  offset = rotate(offset, up, yaw);
  const pitchAxis = rotate(side, up, yaw);
  offset = rotate(offset, pitchAxis, pitch);
  newUp = rotate(newUp, pitchAxis, pitch);
  return { ...camera, position: add(camera.target, offset), up: newUp };
}

/** The closest and farthest the camera may get to its target, in Å. */
export const MIN_DISTANCE = 0.5;
export const MAX_DISTANCE = 5000;

/** The molecule's extent around a camera target: the largest distance of a point from it (at
 * least 1 Å, as autoCamera). */
export function radiusAbout(points: readonly Vec3[], target: Vec3): number {
  let r = 0;
  for (const p of points) r = Math.max(r, norm(sub(p, target)));
  return Math.max(r, 1);
}

/** The server's camera limits (dipolar_app.scene.check_camera), so a move never produces a
 * camera that view.set_camera refuses (round 41). */
const MIN_FOV_DEG = 1;
const MAX_FOV_DEG = 170;
const MIN_NEAR = 1e-3;
const MAX_EXTENT = 1e6;

export function withinLimits(c: Camera): boolean {
  const values = [...c.position, ...c.target, ...c.up, c.fov_deg, c.near, c.far];
  if (!values.every(Number.isFinite)) return false;
  if (Math.max(...[...c.position, ...c.target, c.far].map(Math.abs)) > MAX_EXTENT) return false;
  if (!(MIN_FOV_DEG <= c.fov_deg && c.fov_deg <= MAX_FOV_DEG) || !(MIN_NEAR <= c.near && c.near < c.far)) return false;
  const forward = sub(c.target, c.position);
  const side = cross(forward, c.up);
  return dot(forward, forward) > 1e-12 && dot(side, side) > 1e-12 * dot(forward, forward) * dot(c.up, c.up);
}

/** Moves the camera towards (`factor` < 1) or away from its target. The depth planes are set
 * from the camera's distance and the molecule's extent `radius` alone (as autoCamera: distance ∓
 * 2·radius), never from the previous planes, so zooming in and back out restores them exactly
 * (round 41: carrying a clamped near plane forward clipped atoms). */
export function dolly(camera: Camera, factor: number, radius: number): Camera {
  const offset = sub(camera.position, camera.target);
  const distance = norm(offset);
  const next = Math.min(Math.max(distance * factor, MIN_DISTANCE), MAX_DISTANCE);
  const near = Math.max(next - 2 * radius, MIN_NEAR);
  return {
    ...camera,
    position: add(camera.target, scale(offset, next / distance)),
    near,
    far: Math.max(next + 2 * radius, near * 2),
  };
}

/** `move`'s camera when the server would accept it, otherwise the camera unchanged. */
export function guarded(camera: Camera, moved: Camera): Camera {
  return withinLimits(moved) ? moved : camera;
}

/** Degrees of orbit per pixel dragged, and per arrow key. */
export const DEGREES_PER_PIXEL = 0.5;
export const DEGREES_PER_KEY = 15;
/** Zoom per key press or wheel notch. */
export const ZOOM_STEP = 1.2;

/** The camera move for a key, or null when the key does not move the camera. */
export function keyMove(camera: Camera, key: string, radius: number): Camera | null {
  const moved = move(camera, key, radius);
  return moved === null ? null : guarded(camera, moved);
}

function move(camera: Camera, key: string, radius: number): Camera | null {
  switch (key) {
    case "ArrowLeft":
      return orbit(camera, -DEGREES_PER_KEY, 0);
    case "ArrowRight":
      return orbit(camera, DEGREES_PER_KEY, 0);
    case "ArrowUp":
      return orbit(camera, 0, -DEGREES_PER_KEY);
    case "ArrowDown":
      return orbit(camera, 0, DEGREES_PER_KEY);
    case "+":
    case "=":
      return dolly(camera, 1 / ZOOM_STEP, radius);
    case "-":
    case "_":
      return dolly(camera, ZOOM_STEP, radius);
    default:
      return null;
  }
}

/** The misfit step (0–5) for |residual|/σ: the colour ramp shared by arcs, bars and the plot. */
export function misfitStep(normalized: number): number {
  const z = Math.abs(normalized);
  if (!Number.isFinite(z)) return 5;
  return z < 0.5 ? 0 : z < 1 ? 1 : z < 1.5 ? 2 : z < 2 ? 3 : z < 3 ? 4 : 5;
}

/** An arc's stroke width in pixels: wider for a larger misfit, so the residual is read from width
 * as well as colour (03 §5; colour alone fails for colour-blind readers and in print). */
export function arcWidth(step: number): number {
  return 1.25 + 0.75 * Math.min(Math.max(step, 0), 5);
}

type Point = { readonly x: number; readonly y: number };

/** A quadratic arc from `a` to `b`, bowed sideways by `bend` × its length. Coupling arcs bow so
 * that they do not hide the bonds they run alongside. */
export function arcPath(a: Point, b: Point, bend = 0.18): string {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const cx = (a.x + b.x) / 2 - dy * bend;
  const cy = (a.y + b.y) / 2 + dx * bend;
  const f = (v: number) => (Math.round(v * 100) / 100).toString();
  return `M${f(a.x)},${f(a.y)} Q${f(cx)},${f(cy)} ${f(b.x)},${f(b.y)}`;
}

/** The camera as `view.set_camera` takes it. */
export function cameraIn(camera: Camera): CameraIn {
  return {
    position: { xyz: [...camera.position], unit: "Å" },
    target: { xyz: [...camera.target], unit: "Å" },
    up: { xyz: [...camera.up] },
    fov: { value: camera.fov_deg, unit: "deg" },
    near: { value: camera.near, unit: "Å" },
    far: { value: camera.far, unit: "Å" },
  };
}

/** The scene's shared camera in projection.ts's form. */
export function cameraOf(camera: SceneCamera): Camera {
  return {
    position: [...camera.position.xyz],
    target: [...camera.target.xyz],
    up: [...camera.up],
    fov_deg: camera.fov.value,
    near: camera.near.value,
    far: camera.far.value,
  };
}

type Timers = { set: (fn: () => void, ms: number) => unknown; clear: (handle: unknown) => void };

/** When a camera moved here is committed (rounds 41–42). A gesture's camera is sent once, after
 * `delay` ms of quiet or at once, together with the workspace revision of the camera it started
 * from; the server refuses it if the shared view has moved on (`expected_workspace_revision`).
 * The page also drops it early, never sending it, when it learns of a newer revision from any
 * response (the view and the scene are read separately) or a newer action supersedes it. */
export class CameraCommits {
  private pending: { camera: Camera; revision: number; handle: unknown } | null = null;
  private newest: number;
  private readonly send: (camera: Camera | null, revision: number | null) => void;
  private readonly timers: Timers;

  // No parameter properties: Node's type stripping (tests/view.test.ts) does not support them.
  constructor(revision: number, send: (camera: Camera | null, revision: number | null) => void, timers: Timers) {
    this.newest = revision;
    this.send = send;
    this.timers = timers;
  }

  /** A response showed the shared view at `revision`: a pending camera from an older one is
   * dropped. Revisions only grow, so an older report changes nothing. */
  observe(revision: number): void {
    if (revision <= this.newest) return;
    this.newest = revision;
    if (this.pending && this.pending.revision < revision) this.cancel();
  }

  /** Commits `camera`, moved from the camera shown at `revision`, after `delay` ms of quiet. A
   * camera moved from an already superseded view is not even scheduled. */
  later(camera: Camera, revision: number, delay: number): void {
    this.cancel();
    if (revision < this.newest) return;
    const handle = this.timers.set(() => this.fire(), delay);
    this.pending = { camera, revision, handle };
  }

  /** Commits now, superseding anything pending. `revision` null: unconditionally ("fit to view"
   * moves from no earlier camera). */
  now(camera: Camera | null, revision: number | null): void {
    this.cancel();
    if (revision !== null && revision < this.newest) return;
    this.send(camera, revision);
  }

  cancel(): void {
    if (this.pending) this.timers.clear(this.pending.handle);
    this.pending = null;
  }

  get waiting(): boolean {
    return this.pending !== null;
  }

  private fire(): void {
    const pending = this.pending;
    this.pending = null;
    if (pending && pending.revision >= this.newest) this.send(pending.camera, pending.revision);
  }
}
