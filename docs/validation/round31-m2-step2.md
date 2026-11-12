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
- **Selection after undo or redo** is cleared, even when the restored project is the same
  document. This is deliberate and conservative until projects carry an identity (round 32).
- **The creation and acceptance plans run the steps' parsing under the session lock** (round 32).
- **Undo is not byte-exact.** It restores the science content. The coupling-ID counter keeps its
  high-water mark, so the science hash after an undo can differ from the hash before the undone
  change.

## Round 32 (final under the cap): NOT READY (three A), on commit c664a45

The reviewer confirmed the round-31 pruning-retry fix and found no escalation or deadlock in the
reviewed paths. It found three siblings of the round-31 classes. All are fixed and
mutation-checked, and, under the two-round cap, **not reviewed again**.

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **The history restriction was checked only at creation, before deduplication.** A mixed `[model.set, history.undo]` proposal stored by earlier code still crashed at acceptance (`ValueError`). A keyed creation retried after the rule changed got `INVALID_ARGUMENT` instead of its stored outcome. | Creation now validates inside the plan, after the request-ID check (`_compile`), as acceptance already did. Acceptance refuses a stored proposal that mixes undo or redo with other steps, with a structured `INVALID_ARGUMENT`. Tests: `test_a_stored_mixed_history_proposal_is_refused_not_crashed`, `test_a_retried_creation_returns_its_outcome_even_if_the_rules_changed`. |
| 2 | A | **Loading an older file lowered the coupling-ID counter.** Export, import a pair (`cpl_000015`), undo, load the export (counter back to 15), import another pair: it received `cpl_000015` again. | `keep_allocator`: every replacement (open, import, load, undo, redo) keeps the session's high-water mark. `replace_project` refuses a counter that goes down, so no path can miss it. Test: `test_loading_an_older_file_never_lowers_the_coupling_id_counter`. |
| 3 | A | **Undo and redo kept selected IDs that named other objects.** Open the example, import ethane, select `spn_000001` (H3), undo: the selection stayed `spn_000001`, which is H2 in the example. | A replacement by another document (import, load, open) or by undo or redo **clears** the selection. Edits of the same project (model, torsion, couplings) still prune it to surviving IDs. Tests: `test_another_document_clears_the_selection`, `test_undo_clears_the_selection`. |

**Not reviewed again (cap):**
- The round-32 fixes.
- The creation plan now builds the steps' plans under the session lock. This includes the
  handlers' parsing, such as XYZ text of at most 1 MiB, so a large proposal holds the lock for
  that parsing (B).
- Within a session, coupling IDs are never reused, but the counter can now rise above the loaded
  file's own value. Exporting after a load writes the higher counter (B, harmless).
