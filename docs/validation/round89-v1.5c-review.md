# Round 89: scoped review of the round 88 fixes (GPT-6.2-Sol)

The second and last review of PR #29 under the plan's two-round cap. The owner authorized it
after round 88 was NOT READY ("Fix all, then round 89", 2026-11-25T18:18Z). It is scoped to two
questions: are round 88's nine findings resolved, and did the fixes introduce new blocking
defects?

GPT-6.2-Sol (Codex, reasoning effort high) reviewed `7d94171` against `f89f13e`, on 2026-11-25,
in a tracked-only worktree. Verdict: **NOT READY** (1 A, 1 B). All nine round 88 findings are
resolved.

The report is below, as delivered. Provisional dispositions follow it. After a NOT READY round,
the owner decides how to proceed before any merge.

## Report

### Class A — blocks merge

1. **The guide can save a stale run if the couplings change during the save.**
   - Reproduction: fit a synthetic D6h project and run the guide's snippet. After `run.list`
     returns the selected run as current, replace the couplings through a second `Studio`
     connection, before the snippet calls `run.get`.
   - On the installed wheels, `run.get` returned `run.stale == True`. The snippet still wrote
     the JSON and exited successfully, with `S_zz` estimated and the rank verified.
   - The snippet should check the staleness flag returned with the result before writing it.

   `docs/phase2/reproduce-benzene.md:215`, `packages/dipolar-app/src/dipolar_app/job_ops.py:412`

### Class B

1. **The release notes point to a section that omits the Phase 1 evidence.** The new sentence
   says Phase 1's frozen-result validation, including the published 8CB couplings, is described
   under Validation. The candidate's Validation section describes the synthetic fixed-geometry
   checks and the wheel rehearsal. The Phase 1 evidence is in the 0.1.0b1 notes.
   `docs/release-notes/0.2.0b1.md:69`, `docs/release-notes/0.1.0b1.md:53`

### Round 88 findings

| Finding | Status | Evidence |
|---|---|---|
| A1. Windows paths | Resolved | The regression test failed against the old helper. On the candidate, both Windows paths compiled and retained their backslashes. |
| A2. First-fit gate and allowance | Resolved | The guide requires both ledger entries before any fit, including a trial. At 8–11 decimals it adds the absolute per-condition change, computed with identical couplings, mapping and settings. |
| A3. Stale or unselected run | Resolved | The snippet saved exactly the older `RUN_ID` while a newer run existed. Replacing couplings before invoking the snippet caused refusal without writing a file. An unknown ID was also refused. The new interleaving defect is Class A above. |
| A4. Worksheet record | Resolved | The reviewer built the ten-field record from the worksheet, with all 15 condition keys and both count sets represented as instructed. `check_participant` accepted it and rejected the control with a private note added to a condition. |
| A5. Gate-first order | Resolved | `bb77185` produced 51 passes and seven strict xfails. The implementation removed all seven markers. Its only gate logic change skips the A4 table header's `Key` cell. The original parser rejected the valid table, and the corrected parser still rejected removal of the `participant` row. |
| A6. B10 wildcard | Resolved | Restoring `tags: ["v*"]` produced a hard failure. |
| A7. Guide and worksheet mutations | Resolved | All eight escaped mutations were caught. |
| A8. Disabled release checks | Resolved | All six escaped mutations were caught. The frozen step text and order matched both workflows. |
| B1. Release-notes scope and schedule | Resolved | The notes scope the pending comparisons to V1.5 and make their timing independent of the release. The five page statuses match. The new Phase 1 cross-reference is Class B above. |

### Readings and evidence

- **Checks.** `uv sync --locked` passed. The four requested pytest files gave 441 passed, 0
  failed, 0 skipped. Ruff lint and format passed, with 112 files already formatted. Mypy passed
  across 48 source files. `git diff --check f89f13e 7d94171` passed.
- **A7 mutations.** Each was caught, applied one at a time:
  - continuing after a hash mismatch;
  - mapping H1 to C2;
  - marking D12 as meta;
  - subtracting the rounding allowance;
  - changing `0.05` to `0.50`;
  - asking for public raw reports;
  - removing the `numerical_match` label;
  - asking for a legal name.
- **A8 mutations.** Each was caught, applied one at a time:
  - commenting out the package-version check, the installed CLI version check, or the
    wheel-manifest command;
  - forcing the archive grep status to `1`;
  - adding `|| true` to the release rehearsal;
  - making the wheel-check CLI always return zero.

  Adding `|| true` to the packaged CI rehearsal was also caught.
- **Retired mutation.** Renaming `geometry_computed` in the private Geometry table was missed,
  as the ledger records. Renaming the key in the owner's record table was caught.
- **Build and rehearsal.**
  - Both wheels built, passed the manifest check, and matched the ledger's SHA-256 values.
  - From outside the checkout, a fresh wheel environment passed the isolated smoke test and the
    D6h rehearsal. The synthetic `S_zz` error was `4.4e-11`.
  - The reviewer also followed the guide in the bundled browser app: XYZ import, D6h
    declaration, fixed-model selection, CSV mapping, the fit, and the save by the displayed run
    ID.
- **Disclosure and scope.**
  - The public instructions and notes exposed no corpus coupling or participant details.
  - The prescribed suite compared tracked corpus text for disclosure. It also accessed synthetic
    fixtures it created under temporary `datasets-local/` paths.
  - No owner-local data was accessed, and no experimental fit ran.
  - The reviewer verified the release-note link targets in the candidate tree.

All test and probe data were synthetic. The detached checkout was removed.

## Dispositions (provisional; pending the owner's decision)

| Finding | Disposition |
|---|---|
| A1. Stale run between `run.list` and `run.get` | **Accept.** `run.get` returns the run record (`run.stale`) from the same read as the result. The snippet checks that flag before it writes anything. A gate frozen first requires the check after `run.get` and before the file is written. The rehearsal reproduces the interleaving and requires a refusal. |
| B1. Phase 1 cross-reference | **Accept.** Point to the 0.1.0b1 release notes, by a link pinned to the tag, instead of "under Validation". |
