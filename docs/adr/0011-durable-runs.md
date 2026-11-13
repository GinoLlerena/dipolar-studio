# ADR-0011: Durable runs and stale results (D11)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D11](../03-redesign-plan.md#3-key-decisions)

## Decision

- Atomic chunk + manifest publication (chunks fsynced first); resume validates coverage and content.
- Edits mark earlier results stale; previews carry revision IDs; late responses are discarded.
- Canonical hash over model, observations, covariance, constants version, solver settings, plugins and seed.
- Cross-platform agreement by per-quantity atol + rtol, not byte identity.

## Amendment (M3 step 2, owner's decision): staleness by content

A run or job is **stale when the science differs from its input by content**, not when the
science revision moved. An undo that restores a run's exact input makes the run current again.

- The comparison uses `content_hash`: the science hash without the coupling-ID allocator
  (`next_coupling_id`). Undo deliberately keeps the allocator advanced, so that no coupling ID is
  handed out twice, and the allocator never reaches a fit.
- `content_hash` is derived, never journaled: a job's is computed when its submission is applied
  to the state it computes from, on replay too. If it cannot be derived (the recorded science hash
  does not match), staleness falls back to comparing `science_hash`.
- `science_hash`, `input_hash` and the journal's hashes are unchanged, so existing journals
  replay as before.
- Late *responses* are still recognised by revision (the client's `RevisionMark`); only
  staleness changed.

## Verified by

M2 run tests. The amendment: `test_an_undo_that_restores_a_runs_exact_input_makes_it_current_again` and
`test_an_undo_across_a_couplings_import_also_makes_the_run_current_again` (including replay).
