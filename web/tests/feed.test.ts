// The change-feed client helpers. Run with `pnpm test`.
import assert from "node:assert/strict";
import { test } from "node:test";
import { backoffMs, LineBuffer, MAX_LINE, parseFeedLine, RESOURCES, refreshFor } from "../src/feed.ts";

test("lines split across chunks are joined; blank lines are skipped", () => {
  const buffer = new LineBuffer();
  assert.deepEqual(buffer.push('{"kind":"ping",'), []);
  assert.deepEqual(buffer.push('"cursor":3}\n\n{"kind":"re'), ['{"kind":"ping","cursor":3}']);
  assert.deepEqual(buffer.push('sync","cursor":9}\n'), ['{"kind":"resync","cursor":9}']);
});

test("an endless line is refused", () => {
  const buffer = new LineBuffer();
  assert.throws(() => buffer.push("x".repeat(MAX_LINE + 1)));
});

test("only known feed items with a cursor are accepted", () => {
  assert.deepEqual(parseFeedLine('{"kind":"ping","cursor":4}'), { kind: "ping", cursor: 4 });
  for (const bad of ["", "not json", "null", "[]", '{"kind":"ping"}', '{"kind":"surprise","cursor":1}', '{"kind":"ping","cursor":1.5}']) {
    assert.equal(parseFeedLine(bad), null, bad);
  }
});

const revisions = { science: 1, workspace: 0 };

test("what each feed line makes the page read again", () => {
  assert.deepEqual(refreshFor({ kind: "hello", boot_id: "b", cursor: 0, seq: 0, revisions }), [...RESOURCES]);
  assert.deepEqual(refreshFor({ kind: "resync", cursor: 7 }), [...RESOURCES]);
  assert.deepEqual(refreshFor({ kind: "ping", cursor: 7 }), []);
  assert.deepEqual(refreshFor({ kind: "job", cursor: 7, job_id: "job_000001", status: "running" }), ["jobs"]);
  const commit = (domains: ("science" | "workspace" | "proposal" | "job")[]) =>
    refreshFor({ kind: "commit", cursor: 8, seq: 2, operation: "x", actor: "user", revisions, domains, jobs: [] });
  assert.deepEqual(commit(["workspace"]), ["view"]);
  assert.deepEqual(commit(["science", "workspace"]), ["view", "project", "history", "runs", "jobs"]);
  assert.deepEqual(commit(["job"]), ["view", "runs", "jobs"]);
  assert.deepEqual(commit(["proposal"]), []);
});

test("reconnection backs off from 0.5 s to at most 10 s", () => {
  assert.deepEqual([1, 2, 3, 4, 5, 6, 7].map(backoffMs), [500, 1000, 2000, 4000, 8000, 10000, 10000]);
});
