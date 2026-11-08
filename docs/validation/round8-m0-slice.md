# Validation round 8: the M0 vertical slice

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), read-only. 2026-11-08.
Scope: commit 0c562d8, "M0 step 3: end-to-end vertical slice". The review covered dipolar-core
science, conformance to the 04 contracts, concurrency, HTTP/D10 hygiene, test quality and the
frontend.

## Verdict

**NOT READY** as the M0 step-3 baseline. The science checks passed, but two kinds of problem
remained: live journal failures could break durability, and chunked request bodies bypassed the
memory bound.

## Findings and fixes

All seven findings are fixed. Each fix has a regression test that fails against the pre-fix code
(checked by restoring the old file).

1. **Major. Short journal writes were acknowledged.**
   - The problem: `os.write()`'s return count was ignored.
   - The fix: `Journal.append` now writes until every byte is stored, treats a zero-byte write as
     an error, and fsyncs before returning.
   - Tests: `test_short_writes_are_completed` and `test_zero_byte_write_fails_stop`.
2. **Major. An append failure could leave the session and its journal inconsistent.**
   - The problem: after an fsync failure the live sequence stayed at 0 while the journal held
     sequence 1. A retry then wrote a second sequence 1.
   - The fix is **fail-stop**. After any append failure the outcome is uncertain, so:
     - the in-memory state is left unchanged;
     - every later command returns `JOURNAL_FAILED` (HTTP 503);
     - queries keep answering from the last acknowledged state;
     - a restart replays the journal, which is the source of truth.
   - Tests: `test_fsync_failure_stops_commands_and_restart_follows_the_journal` and
     `test_torn_write_stops_commands_and_is_refused_on_restart`. Recovery of a torn tail stays in
     the M0 step-4 journal spike.
3. **Major. Chunked bodies were buffered without limit.**
   - The problem: without `Content-Length`, `request.body()` read everything before the size
     check.
   - The fix: the adapter now counts bytes while streaming and stops at the 1 MiB limit.
   - Test: `test_chunked_body_is_never_buffered_past_the_limit` (in-process ASGI, bounded so that a
     regression fails rather than exhausting memory).
4. **Minor. Envelope revisions could describe a later snapshot than the result.**
   - The fix: operations read and commit through `Context`, which records the one state they
     observed or produced. The envelope reports exactly that state.
   - Test: `test_envelope_revisions_describe_the_result_snapshot`.
5. **Minor. The frontend accepted late responses.**
   - The fix:
     - previews are sequenced, and only the latest request may update the page;
     - reopening a project invalidates a preview still in flight;
     - view responses with older revisions are discarded.
   - Verified by hand in Chromium (Playwright): the φ = 10° preview was delayed so that it resolved
     after the φ = 20° one, and the page kept φ = 20°. Automated browser tests arrive with M3.
6. **Minor. The science hash omitted numerical provenance (D11).**
   - The fix: `dipolar_core.context.numerical_context()` versions four things: the nuclide table,
     the forward model, the biphenyl template and the inner solver with its rank and admissibility
     policies.
   - The science hash covers that context together with the project. Each journal record stores
     it, and replay refuses a journal written under a different context (a migration is needed).
     `fit.preview` reports it.
   - Test: `test_science_identity_covers_the_numerical_context`.
7. **Minor. The start-up output test had a race.**
   - The problem: the ready file was published before the URL was printed.
   - The fix: publishing the ready file is now the last start-up step.

## Checked and found correct by the reviewer

- **Tests and tooling.** The 75 tests, lint, formatting, strict mypy and TypeScript checks pass.
- **Science.**
  - The design rows match a direct tensor contraction.
  - The diagonal constraint, geometry, K, whitened SVD, minimum-norm solution, rank and condition
    reporting, χ² and admissibility are all correct.
  - The label "profile objective at fixed φ, not a fit" is honest.
- **Contracts.**
  - One dispatcher enforces the credential-derived policy.
  - Unknown fields and units are rejected.
  - Revision checks and command planning run under the writer lock.
  - Replay reproduces hashes and revisions, and reopening a project clears the selection in the
    same transaction.
  - The absolute-set exemption for `view.select` is defensible for the immutable fixture. IDs must
    stay non-reused once broader editing arrives.
- **Localhost and adapters.** The Host and Origin checks, bearer comparison, GET behaviour,
  ready-file permissions and removal, CSP-compatible assets, memory-only fragment token, adapter
  parity and isolated robot execution are all supported by code and tests.
