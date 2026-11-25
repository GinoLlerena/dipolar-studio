# Round 88: review of V1.5c, the benzene guide and the 0.2.0b1 candidate (GPT-6.2-Sol)

The first review of PR #29. GPT-6.2-Sol (Codex, reasoning effort high) reviewed the candidate
`f89f13e` against `f472b16`, with the gate commit `b5063db`, on 2026-11-25, in a tracked-only
worktree. Verdict: **NOT READY** (8 A, 1 B).

The report is below, as delivered. Provisional dispositions follow it. After a NOT READY round,
the owner decides how to proceed before any merge.

## Report

### Class A — blocks merge

1. **The new rehearsal breaks Windows CI.**
   - Reproduction: pass `C:\Users\runner\project` and `C:\Users\runner\saved.json` to
     `the_guides_snippet`, then compile its output.
   - The regex replacement consumes the backslash escaping produced by `json.dumps`, and Python
     raises a truncated `\U` escape error.
   - The Windows job runs the test that invokes this helper.

   `tools/package/rehearse_d6h.py:98`, `.github/workflows/ci.yml:37`
2. **The guide omits two requirements for scored fits.**
   - **The first-fit gate.** Follow Step 3 with the first-fit gate still open: the guide tells
     the participant to fit, although the plan requires approval before the exercise begins.
   - **The allowance.** At 8–11 decimal places, the guide leaves the owner to infer that the
     allowance is the *absolute per-condition change*, computed with identical couplings,
     mapping and settings.

   `docs/phase2/reproduce-benzene.md:154`, `:175`, `docs/phase2/v1.5-plan.md:164`
3. **The save snippet can accept a stale run.**
   - Reproduction: the reviewer fitted one synthetic condition, replaced its observations in the
     same project, and ran the guide's snippet before a fresh fit completed.
   - `run.list` marked the newest completed run stale. The snippet saved it and passed the
     estimated-component and rank assertions.
   - It also always selects the newest run, regardless of which run is selected in the Fit tab.

   `docs/phase2/reproduce-benzene.md:186`
4. **The worksheet's instructions produce a record the checker rejects.**
   - The worksheet says the conditions table is the `conditions` field. Copy a complete
     synthetic row into that field, and `check_participant` returns `condition entries outside
     the closed fields`: each condition entry must contain only `numerical_match`.
   - The worksheet also provides one set of count fields, where Step 4 asks the participant to
     record both sets.

   `docs/phase2/reproduce-benzene-worksheet.md:63`, `:96`, `tools/validation/verification.py:328`
5. **The worksheet assertion changed after the freeze.**
   - Reproduction: delete the `participant` table row and leave its prose mention. The assertion
     from `b5063db` passes, while the amended assertion from `f89f13e` fails.
   - The ledger records this as a correction made in the implementation commit.

   `tests/test_v15c_release.py:363`, `docs/phase2/verification/gates.md:647`
6. **Restoring the old release trigger leaves pytest green.** Replace the three tag patterns with
   `tags: ["v*"]`. B10 enters its original `pytest.xfail` branch, so the exact regression that
   re-enables milestone releases yields an expected failure. `tests/test_v15_gates.py:922`
7. **Guide and worksheet gates accept material instruction changes.** The relevant tests passed
   after each of these edits:
   - telling readers to continue after a hash mismatch;
   - changing H1's carbon, or D12's class;
   - reversing the rounding allowance;
   - changing the paper criterion from `0.05` to `0.50`;
   - asking for raw reports to be posted publicly;
   - removing the `numerical_match` column label;
   - asking for a legal name in prose.

   `tests/test_v15c_release.py:230`, `:298`, `:324`, `:381`
8. **Release gates accept disabled checks.** The assertions passed after each of these edits:
   - commenting out the package-version check, the installed CLI version check, or the build's
     wheel-manifest command;
   - forcing the archive grep status to `1`;
   - appending `|| true` to the release rehearsal;
   - making the wheel-check CLI always return zero.

   `tests/test_v15c_release.py:408`, `:436`, `:487`

### Class B

1. **The release notes overstate the comparison schedule and scope.** The five status fields
   match the report pages.
   - The statement that experimental comparisons run after this release conflicts with the
     plan, which allows V1.5d to proceed in parallel with V1.5c.
   - Scope the status statement to the V1.5 comparisons: Phase 1 already validated against
     frozen results using published 8CB couplings.

   `docs/release-notes/0.2.0b1.md:66`, `docs/phase2/v1.5-plan.md:68`,
   `docs/release-notes/0.1.0b1.md:53`

### Readings and evidence

- **Checks.**
  - `uv sync --locked` passed.
  - The focused suite: 209 passed, 0 failed, 0 skipped.
  - The freeze commit: 5 passed, 33 xfailed, 0 failed, 0 skipped, across the V1.5c file and
    B10.
  - The filtered full suite: 1,758 passed, 0 failed, 3 skipped, 13 deselected, including a pass
    on the 1,000-seed coverage test.
  - Ruff lint, Ruff format, mypy and `git diff --check f472b16 f89f13e` passed.
- **Expected local-data skips.** `test_the_odcb_report_always_carries_both_drop_one_labels`,
  `test_the_local_odcb_inputs_targets_and_roster_when_present`, and
  `test_no_restricted_value_is_in_a_tracked_blob`.
- **Test-scope deviation.**
  - The reviewer started the unfiltered suite before identifying its tracked experimental
    fixtures. It reached 220 passes, including six legacy 8CB fitting cases, before the
    reviewer stopped it.
  - The rerun excluded those cases and seven other cases that process experimental numbers.
  - No experimental benzene fit ran, no corpus coupling values were printed, and no private
    dataset files were accessed.
- **Mutation probes.** Of 33 targeted mutations, 18 were caught and 14 escaped (A7–A8). The
  restored `v*` trigger xfailed.
  - The caught probes:
    - a wrong hash or byte size, the bond radius, the axis sign;
    - a missing copy restriction, a roster label, an orbit pair, the token uncertainty;
    - the guide and module versions, a missing worksheet row, an added phone field, a wrong
      report status;
    - both link-pin regressions, an extra branch trigger, removal of `-I`, and a loosened
      rehearsal tolerance.
  - A separate oldest-run mutation passed the rehearsal, because the project had only one run.
- **Build and installed wheels.**
  - Both wheels built and passed the manifest check, with 40 app entries and 16 core entries.
    Their SHA-256 values matched the ledger.
  - From outside the checkout, the fresh wheel environment passed both the `-I` smoke test and
    the D6h rehearsal. The synthetic S_zz error was `4.4e-11`, and a 1 % perturbation was
    refused.
  - The literal version check, the synthetic negative archive and wheel checks, and the mocked
    draft flags behaved as expected.
- **Answers to the six questions.**
  1. Gate freeze: `b5063db` preceded the implementation. But the worksheet assertion changed in
     `f89f13e`, B10 kept its wildcard xfail, and the mutation probes found coverage gaps.
  2. Guide: the SHA-256, byte size, geometry, axes, 15 labels, orbit mapping, copy rules and
     Step 4 formula match their sources. The UI labels and registry operations exist, and the
     snippet works for a fresh run. A2–A3 cover the scored and reused-project defects.
  3. Disclosure: the added tracked text has no exact corpus coupling or token match, and the
     candidate requests no personal data. The worksheet's nested record instructions conflict
     with the checker.
  4. Workflow: the filters route package tags and exclude milestone tags. The literal version,
     archive, smoke, draft and isolated installed-wheel steps are intact. A1, A6 and A8 cover
     the CI and regression gaps.
  5. Packaging: the checker accepted both real wheels and refused a synthetic excluded member.
     The rehearsal uses independent physical constants and rejected a wrong synthetic answer.
  6. Release notes: the five statuses, the holdout statement, the three robot tutorials and the
     contract version are supported. All nine links point to paths present in the candidate
     tree. The remote `v0.2.0b1` tag was absent, so live tag URLs could not be verified.

All review-specific fitting probes used synthetic data. The detached checkout was removed.

## Orchestrator's notes

- **A1 was already fixed** in `26e8365` before this report arrived, from the Windows CI failure.
  The regression test came first and fails on any platform. Windows CI passes at `26e8365`.
- **The test-scope deviation.** The legacy 8CB cases are Phase 1 regression tests on the tracked,
  published Di Pietro couplings. CI runs them on every push. They are not a V1 fit of the benzene
  or ortho-dichlorobenzene corpus, so the first-fit gate (§3, §10) is not touched. They are
  recorded here so that later briefs name them.

## Dispositions (provisional; pending the owner's decision)

| Finding | Disposition |
|---|---|
| A1. Windows path in the rehearsal | **Accept. Fixed** in `26e8365`, test first. |
| A2. First-fit gate and allowance wording | **Accept.** Before fitting, the guide requires the owner's confirmation that the attempt is logged in the first-fit log (ledger §10, after `freeze approved`). It defines the allowance as the absolute per-condition change, with identical couplings, mapping and settings. |
| A3. Stale or unselected run saved | **Accept.** The snippet saves the run selected in the Fit tab (the shared view's run), and refuses it if it is stale or not the fixed fit. |
| A4. Worksheet against the checker | **Accept.** The conditions table is the participant's private notes. The record's `conditions` takes only the owner's `numerical_match` per condition. The worksheet gets separate rows for the participant's counts (`counts`) and for the published counts. |
| A5. Gate changed in the implementation commit | **Accept.** It is recorded as a correction. Any further gate change lands in a gate commit before the fixes. |
| A6. `v*` still xfails B10 | **Accept.** V1.5c has landed the guard, so the xfail branch is removed, and `v*` fails the gate. |
| A7. Guide and worksheet gates too loose | **Accept.** Each listed mutation gets a gate that catches it. |
| A8. Workflow gates accept disabled checks | **Accept.** The release-critical steps are compared with their frozen text. The build's last command must be the wheel check. The wheel-check CLI is run against a synthetic wheel with an excluded entry, and must exit 1. |
| B1. Release-notes schedule and scope | **Accept.** The status is scoped to V1.5's comparisons. It says they are run by the owner locally, after the gates are frozen, independently of this release. |
