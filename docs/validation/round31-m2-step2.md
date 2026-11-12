# Validation rounds 31–32: M2 step 2 (idempotency, dry run, proposals, undo)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

## Round 31: NOT READY (three A, one B), on commit 92ec004

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **Multi-step proposals containing undo or redo.** A proposal's creation validated each step on a scratch state that updated the history per step, while acceptance commits one record and updates the history once. `[undo, undo]` left an extra undo entry; `[model.set, undo]` passed creation, then acceptance raised `ValueError` ("mixes history kinds"). | `history.undo` and `history.redo` are proposed **alone**: a multi-step proposal containing one is refused at creation (`HISTORY_COMMANDS`). Test: `test_undo_and_redo_are_proposed_alone`. |
| 2 | A | **Undo let a coupling ID be reused.** Undo restored the project's `next_coupling_id`. An import made after the undo could therefore hand out an ID that an earlier, undone import had used, so a cached ID silently named another observation (D5: IDs are never reused). | Undo and redo keep the current allocation high-water mark: the restored project keeps the higher `next_coupling_id`. Test: `test_undo_never_lets_a_coupling_id_be_reused`. |
| 3 | A | **Pruning broke the idempotency of acceptance.** `proposal.accept` looked the proposal up before the commit, so a retry after the proposal had been pruned returned `ID_NOT_FOUND` instead of the stored outcome, even after a restart. | The lookup, the dependency-closure check and the step plans now run inside the plan, after the session's request-ID check. Test: `test_a_retried_acceptance_survives_pruning_and_restart`. |
| 4 | B | **The request table grows for the life of the journal.** Any caller that may issue a command (an agent may set the view directly) can send no-op commands with fresh request IDs. Each is recorded: in the probe, 500 no-ops kept 500 outcomes across a restart, about 406 KB of journal. | Documented below. Bounding it needs a per-actor quota or journal compaction that keeps the retry guarantee. That belongs with snapshots and budgets (D17), after the beta's single-user scope. |

Each fix was mutation-checked: reverting it makes its test fail. The reviewer's other probes passed:
- a journal failure injected before the write, after a durable write, and during a torn write
  recovered correctly;
- the registry matched its snapshot.

## Documented limits (B)

- **Request-table growth** (round 31, finding 4): as above.
- **Not in this step:**
  - compute proposals (`fit.run` from an agent) arrive with jobs in M2 step 3;
  - there is no view undo stack;
  - stale proposals are refused, not rebased;
  - runs from undone states cannot yet be marked stale (there are no stored runs before
    step 3).
- **Undo is not byte-exact.** It restores the science content. The coupling-ID counter keeps its
  high-water mark, so the science hash after an undo can differ from the hash before the undone
  change.

## Round 32

(Pending.)
