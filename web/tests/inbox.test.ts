// The proposal inbox's logic (src/inbox.ts), under Node's test runner.
import assert from "node:assert/strict";
import test from "node:test";
import type { DryRunReport, ProposalOut, StepOut } from "../src/generated/contract.ts";
import {
  acceptBlocker,
  allSteps,
  argsText,
  changeLines,
  closed,
  decidable,
  expired,
  labelled,
  ordered,
  waiting,
  withDependencies,
  withoutDependents,
} from "../src/inbox.ts";

const NOW = Date.parse("2026-11-13T12:00:00Z");

const chain = (n: number): StepOut[] =>
  Array.from({ length: n }, (_, i) => ({ index: i, operation: "model.set", depends_on: i ? [i - 1] : [] }));

const proposal = (over: Partial<ProposalOut> = {}): ProposalOut => ({
  id: "prp_000001",
  proposer: "agent:robot",
  status: "pending",
  stale: false,
  base_science_revision: 4,
  created_at: "2026-11-13T11:00:00+00:00",
  expires_at: "2026-11-14T11:00:00+00:00",
  note: "",
  steps: chain(3),
  decided_by: null,
  decided_at: null,
  accepted_steps: [],
  reason: "",
  ...over,
});

test("pending proposals come first, oldest first; then decisions, newest first", () => {
  const list = [
    proposal({ id: "prp_000003", status: "rejected", decided_at: "2026-11-13T10:00:00+00:00" }),
    proposal({ id: "prp_000005", created_at: "2026-11-13T11:30:00+00:00" }),
    proposal({ id: "prp_000004", status: "accepted", decided_at: "2026-11-13T11:45:00+00:00" }),
    proposal({ id: "prp_000002", created_at: "2026-11-13T09:00:00+00:00" }),
    proposal({ id: "prp_000001", expires_at: "2026-11-13T11:59:00+00:00" }), // pending, but expired here
  ];
  assert.deepEqual(
    ordered(list, NOW).map((p) => p.id),
    ["prp_000002", "prp_000005", "prp_000001", "prp_000004", "prp_000003"], // expiry at 11:59 is the newest closure
  );
  assert.equal(waiting(list, NOW), 2);
});

test("a pending proposal past its expiry is not offered for a decision", () => {
  const p = proposal({ expires_at: "2026-11-13T12:00:00+00:00" });
  assert.equal(expired(p, NOW), true);
  assert.equal(decidable(p, NOW), false);
  assert.equal(decidable(p, NOW - 1), true);
  assert.equal(expired(proposal({ status: "expired" }), 0), true);
});

test("why acceptance is blocked: closed, expired, stale (also by a newer revision seen), nothing chosen", () => {
  const p = proposal();
  assert.equal(acceptBlocker(p, [0, 1, 2], 4, NOW), null);
  assert.equal(acceptBlocker(proposal({ status: "accepted" }), [0], 4, NOW), "closed");
  assert.equal(acceptBlocker(proposal({ expires_at: "2026-11-13T11:00:00+00:00" }), [0], 4, NOW), "expired");
  assert.equal(acceptBlocker(proposal({ stale: true }), [0], 4, NOW), "stale");
  assert.equal(acceptBlocker(p, [0], 5, NOW), "stale"); // the page saw revision 5; the list is older
  assert.equal(acceptBlocker(p, [], 4, NOW), "none-chosen");
});

test("choosing a step chooses what it depends on; unchoosing it drops what depends on it", () => {
  const steps = chain(4);
  assert.deepEqual(withDependencies(steps, [], 2), [0, 1, 2]);
  assert.deepEqual(withDependencies(steps, [0], 0), [0]);
  assert.deepEqual(withoutDependents(steps, [0, 1, 2, 3], 1), [0]);
  assert.deepEqual(withoutDependents(steps, [0, 1, 2, 3], 3), [0, 1, 2]);
  assert.deepEqual(allSteps(steps), [0, 1, 2, 3]);
  // A general graph (the server's rule is dependency closure, not only prefixes).
  const graph: StepOut[] = [
    { index: 0, operation: "a", depends_on: [] },
    { index: 1, operation: "b", depends_on: [] },
    { index: 2, operation: "c", depends_on: [0, 1] },
  ];
  assert.deepEqual(withDependencies(graph, [], 2), [0, 1, 2]);
  assert.deepEqual(withoutDependents(graph, [0, 1, 2], 1), [0]);
  assert.equal(closed(graph, [0, 2]), false);
  assert.equal(closed(graph, [0, 1, 2]), true);
  assert.equal(closed(graph, [1]), true);
});

test("arguments are shown as JSON text, cut when long", () => {
  assert.deepEqual(argsText({ a: 1 }), { text: '{\n  "a": 1\n}', cut: 0 });
  const long = argsText({ csv: "x".repeat(5000) }, 100);
  assert.equal(long.text.length, 100);
  assert.equal(long.cut, JSON.stringify({ csv: "x".repeat(5000) }, null, 2).length - 100);
});

test("IDs are named by their labels when known, own properties only", () => {
  assert.deepEqual(labelled(["cpl_000001", "cpl_000009", "toString"], { cpl_000001: "H2–H3" }), [
    "H2–H3 (cpl_000001)",
    "cpl_000009",
    "toString",
  ]);
});

const report = (over: Partial<DryRunReport> = {}): DryRunReport => ({
  proposals_changed: ["prp_000001"],
  science: null,
  selection_after: null,
  would_revisions: { science: 4, workspace: 2 },
  ...over,
});

const ids = (over = {}) => ({ added: [], removed: [], changed: [], n_added: 0, n_removed: 0, n_changed: 0, truncated: false, ...over });

test("what acceptance would change, as lines", () => {
  assert.deepEqual(changeLines(report(), {}), [{ kind: "nothing" }]);
  // A dry run does not report jobs: a fit the steps would start is counted from the operations.
  assert.deepEqual(changeLines(report(), {}, ["fit.run"]), [{ kind: "jobs", count: 1 }]);
  const lines = changeLines(
    report({
      science: {
        science_hash_before: "a",
        science_hash_after: "b",
        project_opened: false,
        name_changed: false,
        geometry_changed: false,
        model_changed: true,
        spins: ids(),
        couplings: ids({ changed: ["cpl_000001"], n_changed: 1, removed: ["cpl_000002"], n_removed: 1 }),
      },
      selection_after: [],
    }),
    { cpl_000001: "H2–H3" },
  );
  assert.deepEqual(lines, [
    { kind: "model" },
    { kind: "couplings", change: "removed", count: 1, names: ["cpl_000002"], truncated: false },
    { kind: "couplings", change: "changed", count: 1, names: ["H2–H3 (cpl_000001)"], truncated: false },
    { kind: "selection", names: [] },
  ]);
  const opened = changeLines(
    report({
      science: {
        science_hash_before: "a",
        science_hash_after: "b",
        project_opened: true,
        name_changed: true,
        geometry_changed: true,
        model_changed: true,
        spins: ids(),
        couplings: ids(),
      },
    }),
    {},
  );
  assert.deepEqual(opened, [{ kind: "opened" }]); // opening says it all
});
