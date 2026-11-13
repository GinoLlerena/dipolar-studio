// Couplings CSV reconciliation helpers (src/reconcile.ts), under Node's test runner.
import assert from "node:assert/strict";
import test from "node:test";
import type { ReconcileOut } from "../src/generated/contract.ts";
import { blocker, collisions, effectiveMapping, labelsOf, sameMapping } from "../src/reconcile.ts";

const diff = (over: Partial<ReconcileOut> = {}): ReconcileOut => ({
  added: [],
  changed: [],
  complete: true,
  ignored_columns: [],
  proposed_mapping: { H2: "spn_000001", H3: "spn_000002" },
  removed: [],
  science_hash: "sha256:x",
  science_revision: 4,
  unchanged: [],
  unmatched_labels: [],
  unresolved_pairs: [],
  ...over,
});

test("the file's labels: matched and unmatched, sorted, once each", () => {
  assert.deepEqual(labelsOf(diff({ unmatched_labels: ["Ha", "H2"] })), ["H2", "H3", "Ha"]);
});

test("the user's choices override the proposal; an empty choice unmaps a label", () => {
  const proposed = { H2: "spn_000001", H3: "spn_000002" };
  assert.deepEqual(effectiveMapping(proposed, {}), proposed);
  assert.deepEqual(effectiveMapping(proposed, { Ha: "spn_000003", H3: "" }), { H2: "spn_000001", Ha: "spn_000003" });
});

test("two labels on one spin are a collision", () => {
  const clash = collisions({ H2: "spn_000001", H3: "spn_000001", H4: "spn_000004" });
  assert.deepEqual([...clash], [["spn_000001", ["H2", "H3"]]]);
  assert.equal(collisions({ H2: "spn_000001" }).size, 0);
});

test("the import waits for a complete, current diff of exactly this mapping", () => {
  const d = diff();
  const m = d.proposed_mapping;
  const labels = labelsOf(d);
  assert.equal(blocker(null, null, m, labels, 4), "no-file");
  assert.equal(blocker(d, m, m, labels, 4), null);
  assert.equal(blocker(d, m, { H2: "spn_000001" }, labels, 4), "unmapped");
  assert.equal(blocker(d, m, { H2: "spn_000001", H3: "spn_000001" }, labels, 4), "collision");
  assert.equal(blocker(diff({ unresolved_pairs: ["Hx-Hy"] }), m, m, labels, 4), "unresolved");
  // A diff checked for another mapping, at another revision, or incomplete, cannot be imported.
  assert.equal(blocker(d, m, { H2: "spn_000002", H3: "spn_000001" }, labels, 4), "outdated");
  assert.equal(blocker(d, m, m, labels, 5), "outdated");
  assert.equal(blocker(diff({ complete: false }), m, m, labels, 4), "outdated");
});

test("mappings compare by every entry", () => {
  assert.ok(sameMapping({ a: "1", b: "2" }, { b: "2", a: "1" }));
  assert.ok(!sameMapping({ a: "1" }, { a: "1", b: "2" }));
  assert.ok(!sameMapping({ a: "1", c: "2" }, { a: "1", b: "2" }));
});
