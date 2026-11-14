// The reply check of src/api.ts (M3 step 4, round 49), under Node's test runner.
import assert from "node:assert/strict";
import test from "node:test";
import { asEnvelope } from "../src/api.ts";

const success = {
  ok: true,
  operation: "run.get",
  result: { result: {} },
  revisions: { science: 3, workspace: 1 },
  replayed: false,
  dry_run: null,
};

test("a complete success or error envelope is passed through", () => {
  assert.equal(asEnvelope(success, 200), success);
  const refused = { ok: false, operation: "run.get", error: { code: "ID_NOT_FOUND", message: "no such run" } };
  assert.equal(asEnvelope(refused, 404), refused);
});

test("anything else becomes an INTERNAL error envelope (round 49)", () => {
  const bad = [
    undefined, // not JSON
    null,
    "text",
    { ok: false }, // no error body
    { ok: true, result: {} }, // round 49: no operation, revisions or dry_run
    { ...success, result: null },
    { ...success, revisions: { science: "3", workspace: 1 } },
    { ...success, operation: undefined },
    (({ dry_run: _, ...rest }) => rest)(success),
  ];
  for (const body of bad) {
    const envelope = asEnvelope(body, 502) as unknown as { ok: boolean; error: { code: string; message: string } };
    assert.equal(envelope.ok, false, JSON.stringify(body));
    assert.equal(envelope.error.code, "INTERNAL");
    assert.match(envelope.error.message, /not an operation envelope \(HTTP 502\)/);
  }
});
