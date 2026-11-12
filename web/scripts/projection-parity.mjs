// Projection parity (04 §8.4): the browser's projection (src/scene/projection.ts) must place every
// fixture point where the Python renderer does (dipolar_app.scene, parity-fixtures.json).
// Run: node --experimental-strip-types scripts/projection-parity.mjs   (exit 1 on any mismatch)
import { readFileSync } from "node:fs";
import { autoCamera, drawOrder, project } from "../src/scene/projection.ts";

const fixtures = JSON.parse(readFileSync(new URL("../src/scene/parity-fixtures.json", import.meta.url), "utf8"));
const tol = fixtures.tolerance_px;
const failures = [];
let worst = 0;
const close = (a, b, what) => {
  const d = Math.abs(a - b);
  worst = Math.max(worst, d);
  if (!(d <= tol * Math.max(1, Math.abs(b)))) failures.push(`${what}: ${a} vs ${b}`);
};

for (const c of fixtures.cases) {
  const [w, h] = c.viewport;
  if (c.auto) {
    const cam = autoCamera(c.points, w, h, c.camera.fov_deg);
    for (const key of ["position", "target", "up"]) cam[key].forEach((v, i) => close(v, c.camera[key][i], `${c.name}: camera.${key}[${i}]`));
    for (const key of ["fov_deg", "near", "far"]) close(cam[key], c.camera[key], `${c.name}: camera.${key}`);
  }
  const got = project(c.camera, w, h, c.points);
  got.forEach((p, i) => {
    const e = c.expected[i];
    if (p.visible !== e.visible) failures.push(`${c.name}: point ${i} visible ${p.visible} vs ${e.visible}`);
    close(p.depth, e.depth, `${c.name}: point ${i} depth`);
    if (e.visible) {
      close(p.x, e.x, `${c.name}: point ${i} x`);
      close(p.y, e.y, `${c.name}: point ${i} y`);
    }
  });
  const order = drawOrder(c.ids, got);
  if (JSON.stringify(order) !== JSON.stringify(c.draw_order)) failures.push(`${c.name}: draw order ${order} vs ${c.draw_order}`);
}

if (failures.length) {
  console.error(`projection parity FAILED (${failures.length}):\n` + failures.join("\n"));
  process.exit(1);
}
console.log(`projection parity OK: ${fixtures.cases.length} cases, largest difference ${worst.toExponential(2)}`);
