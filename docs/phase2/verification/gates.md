# V1.5 gate ledger

The V1.5a ledger of the Phase 2 verification step ([plan](../v1.5-plan.md), reviewed by Claude
Opus in [v1.5-plan-review.md](../../validation/v1.5-plan-review.md)). It is appended, not
edited: a correction is a new dated entry. It names restricted material only by dataset,
condition, count, precision and SHA-256.

- **Baseline:** `main` at `57307e9a8610efb990a99cd44bff6d3df92b4bb5` (after `v1.4-browser`).
- **Protocol revision (V0.3):** `332be1d699421d568655669a9fcaf2fc05667e195795a63913b9a67d22e48ea3`
  (`prereg.protocol_sha256`, amendment ledger empty).

## 1. Owner decisions

Approved by the owner in the orchestrating session on 2026-11-21. Recorded at
**2026-11-21T14:59Z** (UTC), before any V1 fit of experimental data. Sol (GPT-6.2-Sol) and
Claude (Opus) drafted each recommendation independently. They agreed on all of them except
decision 7, where Claude accepted Sol's choice. The owner accepted every recommendation.

| # | Decision | Disposition | Consequence |
|---|---|---|---|
| 1 | Benzene comparison reference | **A.** The outside participant compares against the published project cell counts. The owner checks every numerical fit privately on the owner's laptop. | Together these satisfy project decision 6 without publishing any numerical reference beyond V0.3 §6. |
| 2 | External success criterion | **A.** Independent source-to-fit provenance for all 15 benzene conditions, a numerical match for each under the plan's full-precision rule, and all 15 paper comparisons completed, with the published counts reproduced. | A disagreement with the paper is recorded and reviewed. It does not fail the software reproduction. |
| 3 | Spot-check reporting rule | **A.** Each experimental comparison (benzene and ortho-dichlorobenzene) stays `pending` until that dataset's spot-check receipt is signed. Until then the runner passes `target=None`. The ODCB spot-check note stays visible. | Stricter than V0.3 §7, which let ODCB be compared with the note. See amendment draft P-2. |
| 4 | Four-value verification crosswalk | **A.** `partially supported` → `pending` (with counts). `explained discrepancy` → `unresolved failure`, annotated "explained, reviewed". `pending`, `experimentally supported` and `unresolved failure` are unchanged. The exact V0.3 label and counts are printed beside it. | Only a fully supported comparison earns `experimentally supported`. This is a V1.5 reporting rule: the V0.3 label is kept as frozen, so no V0.3 amendment is needed. |
| 5 | Restricted discrepancy review | **B** (fallback). The owner states that no second person has authorized local access. The owner writes value-free public entries and a local numeric annex. A fresh Sol reviews the public entries. A deterministic local script checks exact one-to-one coverage. The owner attests to the numeric record. | Needs a disclosure amendment before the first fit (decision 5a, amendment draft P-1). The exit audit states that only the owner saw the numbers. |
| 5a | Public entry disclosure scope | **A.** A public entry names the dataset, track, cell (condition and estimand) and protocol revision, and gives the scientific context and suspected cause. It carries no target, fit, signed difference, margin or other number from which one could be recovered. | Sol's review can check each entry's reasoning. Needs amendment P-1 to V0.3 §6 before the first fit. |
| 6 | V1 pre-release | **A.** Publish the verified `v0.2.0b1` draft during V1.5c and use it for the outside exercise. | A later change that affects installation or reproduction needs a new package version (`0.2.0b2` …) and a rerun on it. Earlier evidence is kept. |
| 7 | 8CB beta release | **A.** The 8CB testers use the Phase 1 `v0.1.0b1` wheels and `docs/beta/testers.md` pinned to that tag. Beta fixes go on `release/0.1`. | `v0.1.0b1` is still a GitHub draft (checked 2026-11-21). The owner publishes it before recruiting 8CB testers. |
| 8 | Outside participant eligibility | **A.** Excluded: the owner; the 1998 co-authors (Gino Llerena, Marco Idrogo) and advisor (Dr. Jaime Avalos); Dipolar Studio contributors; anyone who prepared the exercise or had advance access to the reference result. | At least one qualifying benzene participant and two independent 8CB testers. |
| 9 | Evidence channel | **A.** Private owner intake. The owner posts a sanitized receipt keyed by an opaque participant ID. | No names, GitHub handles, contact details or raw attachments in the repository. |
| 10 | Figshare checksum mismatch | **A.** Stop the scored attempt and retry the publisher's versioned file or the manifest's original download URL until the recorded SHA-256 matches. **B** (a documented source correction or amendment, then restart) only after investigation. | The scored exercise uses the verified original bytes, including line endings. |
| 11 | Laptop scan operator | **A.** The owner runs each staged-index scan and signs its receipt. | Every commit, including this one, waits for the owner's scan of the exact staged tree (`git write-tree`). |

## 2. V0.3 amendments

**Approved by the owner, recorded at 2026-11-21T15:32Z** (UTC), before any V1 experimental
fit, and entered in `v0.3-preregistration.json` `amendments` and V0.3 §8.

Both are `kind: protocol`, `post_hoc: false`. Neither changes a
number in the JSON, so `protocol_before_sha256` equals `protocol_after_sha256` (the revision
above). The rules they change live in V0.3 §6–§7 and in the V1.5 runner, and the V1.5b gates
test them. *Open for review:* whether to add a closed JSON field instead, so that the protocol
revision changes with them.

- **P-1 (disclosure, decision 5a).** V0.3 §6 is extended: besides `prereg.shareable`, a
  reviewed discrepancy entry may be shared that names the dataset, comparison track, condition,
  estimand and protocol revision of a disagreeing cell, with its scientific context (estimand,
  frame and observable convention, geometry, vibrational corrections, solvent and sample) and
  the suspected cause. It carries no target, fit, signed difference, margin, or ratio from which
  one could be recovered. The cell-level numbers stay in the local annex. *Reason:* no second
  person has authorized local access, so an independent review of a discrepancy is possible only
  on a value-free public entry.
- **P-2 (spot-check gating, decision 3).** V0.3 §7 is tightened: until a dataset's spot-check
  receipt is signed (bound to the checked file's SHA-256), its targets are treated as absent
  (`pending/no-target`) in both comparison tracks. `rank-unverified` keeps its precedence. The
  ODCB spot-check note stays on its label while the check is open. *Reason:* the owner's
  transcription decision. A comparison must not rest on an unchecked transcription.

## 3. Chronology (first-fit gate)

| Field | Value |
|---|---|
| No-fit attestation for V1.5 work | **Owner to sign:** "No V1 fit of experimental data has been run by anyone for V1.5 before this entry." Exposure checked against [exposure-log.md](../exposure-log.md). |
| Decisions approved | 2026-11-21T14:59Z (§1) |
| V0.3 amendments P-1, P-2 approved | 2026-11-21T15:32Z (§2) |
| V1.5a gates frozen | pending |
| First experimental fit submission (UTC, release or commit, protocol revision, dataset, runner role) | empty |
| First access to any V1 experimental result (UTC) | empty |

Until the V1.5a gates are frozen, only synthetic data (the D6h rehearsal and the existing
synthetic datasets) is fitted, by the owner, by every agent and by any participant.

## 4. Owner actions outstanding

- Sign the no-fit attestation (§3).
- Sign the receipt of each staged-index scan (decision 11, as changed in §6).
- Sign the benzene and ortho-dichlorobenzene spot-checks (`SPOT-CHECK.md` under
  `datasets-local/`). The benzene one gates V1.5e.
- Publish the `v0.1.0b1` draft before the 8CB testers start (decision 7).
- Recruit one benzene participant and two 8CB testers (decision 8).
- Before any cell identity is published under P-1 (round 81, B): record a rights check that
  naming a disagreeing cell discloses no restricted value of its source, for each dataset.
- Append the `freeze approved` row to the first-fit log (§10) when the gates are frozen, then
  log each submission there, and commit it, before running it (round 83, A1). The runner
  authorizes no fit before that.
- If the library requests succeed, write each dataset's method-evidence record under
  `datasets-local/` (`verification.py --method`, round 83, A4), naming where the source documents
  each input. Without it the authors'-analysis track stays pending.
- For each disagreeing cell, write its annex entry and review receipt under `datasets-local/` and
  pass their references with `--reviews` (round 83, A5). Round 84: the annex entry has the plan's
  six fields, and each receipt links its own public heading, which has a body.
- Keep every file under `datasets-local/verification/`, including `retained/` and `reports/`.
  The scan checks the whole chain of runs, so deleting a run's record or report fails it
  (round 84, A6).

## 5. Frozen gates

| Gate | Test | Evidence |
|---|---|---|
| Collinear rank-1 recovery (plan, V1.5a; review B2) | `tests/test_core_fixed.py::test_v15a_collinear_rank_1_recovers_the_contraction` (axis-aligned and rotated) | Passes on `57307e9`'s fitter. A mutation check (2026-11-21) injected four defects: a contraction off by 1e-6, a claimed estimated component, a claimed verified rank, and predictions off by 1e-6 Hz. Each failed the gate in both frames. |
| Four-value verification field and crosswalk (decision 4) | `tests/test_v15_gates.py`: the four values, every V0.3 label mapped, anything else refused | Strict xfail until V1.5b adds `tools/validation/verification.py`. |
| Five pages, one valid field each | `tests/test_v15_gates.py::test_every_page_carries_exactly_one_verification_field` (benzene, ODCB and 8CB `pending`; both synthetic pages `synthetic-only`), plus refusals | Strict xfail until V1.5b writes the pages. |
| First-fit chronology (A1, §3) | `tests/test_v15_gates.py`: an open decision, a fit during the freeze (including at the approval instant), the earliest submission across datasets, and amendment classes `pre-fit`, `after-submission` and `post hoc` (an unknown access time counts as post hoc) | Strict xfail until V1.5b. |
| Release-trigger guard (B10) | `tests/test_v15_gates.py`: package tags trigger; milestone and malformed tags do not | The filter reader is checked against GitHub's syntax. Package tags pass now. The milestone cases are a strict xfail until V1.5c. On 2026-11-22 the current `v*` triggered all nine milestone and malformed tags, and the plan's three package patterns triggered none of them and all seven package tags. |

Still to freeze, with V1.5b's tests (plan, V1.5b column): missing or skipped local evidence and
unsupported success claims in the exit checks, receipts, roster completeness and the
restricted-fit scan tier.

## 6. Later entries

- **2026-11-21T15:33Z, decision 11 changed from A to B.** The owner asked Claude (the
  orchestrator) to run the staged-index scan on the owner's laptop. Scope: the scan entry point
  only (`pytest tests/test_v0_preregistration.py -k no_restricted_value_is_in_a_tracked_blob`,
  plus `git diff --cached --check` and an empty `git ls-files -- datasets-local/`). Claude reports
  pass or fail with value-free `path:line` diagnostics, and does not open the local input files
  or raw logs. Each scan is bound to its `git write-tree` and recorded below. The owner remains
  responsible for the receipts.

| UTC | Staged tree | Scan | Operator |
|---|---|---|---|
| 2026-11-21T15:34Z | `544f718b8c221c96e9feb667f48f6bd2c6b50ac6` (commit `241e8ed`) | passed, not skipped | Claude |
| 2026-11-22T16:08Z | `55227c7b0fe72873c7b0d55e0a023c59f8237ff5` (commit `d5f5aa3`) | passed, not skipped | Claude |
| 2026-11-22T16:24Z | `be08fce817d23ab758eb26767e734129ccf7f3d3` (commit `cad9342`) | passed, not skipped | Claude |
| 2026-11-22T16:26Z | `46865eecdb39ad123ba1b6eaf919300ff479874b` (commit `016a56a`) | passed, not skipped | Claude |
| 2026-11-22T17:20Z | `bb23b01d5eb136482391097d52e43eef94e0c048` (commit `76f4aba`) | passed, not skipped | Claude |
| 2026-11-22T17:22Z | `31cd0fe992daba9e652d7d0fbdd52fa863c4db34` (commit `1382313`) | passed, not skipped | Claude |
| 2026-11-22T20:32Z | `491ac4dfdaaebc5a916e135cf4a11381f387a1e8` (commit `5b219c4`) | passed, not skipped | Claude |
| 2026-11-22T22:16Z | `21e153040a21075f1627543d70a9178cc2dbc0d9` (commit `0795f47`) | passed, not skipped | Claude |
| 2026-11-22T22:33Z | `056b50b005c3c51025562a0f2e220781d154bb69` (commit `1654d64`) | passed, not skipped | Claude |
| 2026-11-23T14:11Z | `e2e08c4417bee3dc4b13a6bf820196aaaefccb0a` (commit `13f41cb`) | passed, not skipped | Claude |
| 2026-11-23T14:32Z | `da39310621d06ad536cad92fea31b0bdd2acb195` (commit `b413038`) | passed, not skipped; fit tier: pre-result | Claude |
| 2026-11-23T14:44Z | `51a4b9b4c2188839586ec248106bd8a01312fe69` (commit `1ad0fd4`) | passed, not skipped; fit tier: pre-result | Claude |
| 2026-11-23T15:15Z | `0b79bdfebd5e1db1e3b91380b7188f0ce147c713` (commit `f2ef4d0`) | passed, not skipped; fit tier: pre-result | Claude |
| 2026-11-23T15:30Z | `0eda6177587680bb29bb4efc7bf4c0372eeda034` (commit `0ab5e5e`) | passed, not skipped; fit tier: pre-result | Claude |
| 2026-11-23T19:27Z | `9cfb4bdda7e45398ae2f3becc2c9bbe615020707` (commit `45f54a8`) | passed, not skipped; fit tier: pre-result | Claude |
| 2026-11-23T20:03Z | `3caa4572f249c978e7fc0dcf2dda65feedb58f4f` (commit `e74081d`) | passed, not skipped; fit tier: pre-result | Claude |
| 2026-11-23T20:12Z | `9e47637cf8d4f598b2556ae4f7350f38a1c438b1` (commit `35c0f9f`) | passed, not skipped; fit tier: pre-result | Claude |
| 2026-11-23T22:24Z | `41319233761248908f7c133c7377f2889bc609a7` (commit `46a1f2c`) | passed, not skipped; fit tier: pre-result | Claude |
| 2026-11-23T22:56Z | `613fbb884214948378ef3b6a29b265c53d939655` (commit `9ca2803`) | passed, not skipped; fit tier: pre-result | Claude |
| 2026-11-24T23:18Z | `e60d96ce98144c189fa14940b24f81087cb32f7d` (commit `0fac7e8`) | passed, not skipped; fit tier: pre-result | Claude |
| 2026-11-24T23:41Z | `0cc589221cbcada2a2cd68da921bad9b9df90a1a` (commit `a435803`) | passed, not skipped; fit tier: pre-result | Claude |

Each receipt is first recorded in its commit's message: a tree cannot contain its own hash. Its
row is appended here in the next commit.

- **2026-11-22T14:11Z, no-fit attestation signed** by the owner: "No V1 fit of experimental data
  has been run by anyone for V1.5 before this entry." Exposure was checked against
  [exposure-log.md](../exposure-log.md): its last entry (2026-11-19) records no V1 fit. This
  completes the §3 row and the first §4 action.
- **2026-11-22, round 81 correction (A6).** Commit `d5f5aa3` edited the §3 attestation row and
  removed the §4 action in place, against this ledger's append-only rule. Both are restored to
  their `241e8ed` text, and the entry above records the signature.
- **2026-11-22, protocol revision (round 81, A7).** Amendments P-1 and P-2 are now closed fields of
  the JSON's `reporting` object, so they change the revision. The original is
  `332be1d699421d568655669a9fcaf2fc05667e195795a63913b9a67d22e48ea3` (the header above). After P-1
  it is `1b12b8f474df4433e8089fbca63e0208480c3438acf3a8c1964a8d61c2dae714`, and after P-2
  `a27e0921851193ff1f3845d1bee4ccf42a8f21e4173cbf63d7df6d598fc6a4c5`, the current revision (V0.3
  §8). §2's "*Open for review*" is decided: closed fields.
- **2026-11-22, decision 8 by role (round 81, B).** From here on this ledger refers to the people
  decision 8 excludes by role: the 1998 thesis co-authors and their advisor. They stay credited for
  the 1998 work in the README and `CITATION.cff`.
- **2026-11-22, frozen gates (round 81).** The items §5 deferred to V1.5b ("missing or skipped
  local evidence and unsupported success claims", and the participant precision rule) are frozen
  now, in §7–§8. Runner-level roster, receipt, gated-target and restricted-fit scan tests stay with
  V1.5b, as the plan assigns them. The pending gates no longer use strict xfails. A V1.5b gate
  xfails only while `tools/validation/verification.py` is missing, and the workflow gate only
  while `release.yml` keeps `v*`. `pytest -rx` lists them.

- **2026-11-22, V1.5b report workflow (for review).** The gates in `tests/test_v15_verification.py`
  were frozen in commit `0795f47`, before the implementation. Two readings of the frozen text are
  open for the reviewer:
  - **Reproduction with undocumented corrections.** V0.3 §6 requires all four inputs for a
    reproduction claim, and uses the fallback when "the geometry is obtained but the weights or
    the objective are not". With the geometry, objective and weights documented but the
    corrections not, neither applies. `prereg_labels.reproduction_mode` returns `pending`.
  - **The o-DCB declared geometry places no chlorine.** V0.3 §2: "chlorine enters no coupling".
    The fit imports the six carbons and the four protons only. The couplings and the C2v
    declaration do not depend on chlorine.
  No experimental coupling has been fitted. Every V1.5b test uses synthetic files under a
  temporary root.

- **2026-11-23, V1.5b part 2 gates frozen (for review).** Before their implementation:
  - **The restricted-fit scan tier** (`tests/test_v15_fit_tier.py`). Its source is the report
    workflow's full-precision fit values in `datasets-local/verification/<dataset>.fit-values.json`.
    The declared variants: each value as written and at 4–8 significant digits (half-up,
    half-even, truncated) in any path, and at 3 significant digits in the Phase 2 and validation
    docs. The §3 first-fit row decides when it is required: `pre-result` while that row is
    `empty` and no local fit output exists, `results` after. Its problems are value-free. From
    the implementation on, each scan row below records the tier's status.
  - **The four-site-jump robot tutorial** (`packages/dipolar-app/tests/test_app_v15_jump4.py`).
    Synthetic jump4 couplings with a known answer. The agent proposes, a human accepts, the robot
    waits and reports the complete `run.get` result. A rejection or no decision ends it without
    a fit.

- **2026-11-23, the restricted-fit scan tier is in force.** The decision-11 command now runs the
  whole staged check (`restricted_scan.check_staged`), fit tier included. From
  `FIT_TIER_SINCE` (2026-11-23T14:30Z) each scan row records the tier's status, which
  `uv run --locked python tools/datasets/restricted_scan.py` prints without any value. Until the
  §3 first-fit row is filled the status is `pre-result`. After the owner logs the first fit, the
  report workflow's `datasets-local/verification/<dataset>.fit-values.json` must exist before any
  scan can pass.

- **2026-11-23, round 83 gates frozen (A1–A3, A6, B1), before the fixes.** New:
  `tests/test_v15_first_fit_log.py` (the §10 first-fit log, the runner's authorization, the
  command's refusal without a committed, logged submission) and round 83 regressions at the end
  of `tests/test_v15_verification.py` (linked local paths, protocol validation before any fit,
  provenance). Amended in `tests/test_v15_fit_tier.py`: a fit is logged in §10, not by the §3
  row; the staged check reads the staged ledger and refuses a log that drops a committed row;
  each logged submission needs its own output, bound to it, covering the roster exactly and
  retained across reruns; diagnostics never repeat a key or file name; every receipt row is well
  formed and the first one under the tier is pinned. The amendment strengthens the frozen gate.
  It removes no case that the gate rejected before. §10 is new and append-only. Its first four
  rows transcribe earlier entries. The owner adds the `freeze approved` row. Until then the
  runner authorizes no fit.

- **2026-11-23, round 83 fixes (A1–A3, A6, B2).**
  - **A1.** `tools/validation/first_fit_log.py` reads §10. `verification.authorize` requires a
    `freeze approved` row, a chronology that `freeze_ok` accepts, the owner or a participant, a
    submission logged with exactly its fields, and a time not in the future. The command reads
    the committed ledger (`git show HEAD:…`) and fits nothing without that authorization.
  - **A2.** The fit tier requires, for each logged submission, a complete output bound to it.
    Reruns keep earlier outputs under `retained/`.
  - **A3.** Local writes refuse linked directories and replace, never follow, a linked file.
    Diagnostics never print a key or an unexpected file name.
  - **A6.** The closed schema and `prereg.validate` run before any fit. The local report keeps
    each fit's provenance.
  - **B2.** The robot documents the ready file's credential boundary.

  Two tests were added after the gate commit, for mutants that survived it: an edited committed
  log row, and a record at another revision than its submission. Two other surviving mutants are
  redundant guards: another check raises the same problem. One read in the gate's own test file
  named no encoding (`tests/test_boundaries.py` caught it). It now names UTF-8. Findings A4 and
  A5 follow separately.

- **2026-11-23, round 83 gates frozen (A4, A5), before the fixes.** Added at the end of
  `tests/test_v15_verification.py`: the authors'-analysis track run from an owner-local
  method-evidence record. All four inputs documented give a reproduction, fitted with the authors'
  ring radii and the documented weights, with the printed token's table margin or the 2p figure
  margin. The geometry without the objective or the weights gives the frozen fallback (1/σ²)
  under its own label. Anything else stays pending, with no second fit. P-2 withholds this track's
  targets until the spot-check is signed, and an unverified rank keeps its precedence, signed or
  not. A malformed record, or a printed token that is not its target, blocks before any fit. This
  track's disagreements need their own reviews. Its values stay local and enter the fit-values
  record. Amended: review evidence is a reference (path and SHA-256) to an existing local annex
  entry and to a local review receipt that links a reviewed public entry by path, SHA-256 and
  heading. Each file is bound to the dataset, track, cell and protocol revision. Matching keys
  alone, and missing, stale, unbound, linked or misplaced files, leave the failure unresolved.
  Added to `tests/test_v15_fit_tier.py`: the scan covers the reproduction values, roster-exact.
  These tests xfail while `tools/validation/evidence.py` is absent. The amendment strengthens the
  frozen gate. It removes no case that the gate rejected before.

- **2026-11-23, round 83 fixes (A4, A5).**
  - **A4.** `tools/validation/evidence.py` reads the owner-local method-evidence record
    (`verification.py --method`). It refuses, before any fit, a record that is not for this
    dataset and revision, or that this runner cannot express: the authors' geometry is the
    protocol's shape with the authors' two radii, the objective is least squares, the weights are
    1/σ² or uniform, and the corrections are an empty list. `run_report` fits the authors'
    analysis only in `reproduction` or `fallback` mode (the fallback always uses 1/σ²). The
    margins come from the printed token of the hash-verified targets file, which must print the
    target's value, or are 2p. P-2 and rank precedence apply on this track. Its disagreements
    join the review keys, and its fits and discrepancies enter the local report and the
    fit-values record. The scan requires roster-exact coverage of those values when present.
  - **A5.** A disagreement counts as reviewed only when each key has one annex reference and one
    receipt reference. The annex reference must reach an existing, current annex entry under
    `datasets-local/`. The receipt reference must reach a local receipt that links the reviewed
    public entry (outside `datasets-local/`) by path, SHA-256 and a heading line. Every file must
    be bound to the key and reached through no link.

  One gate test was corrected after the gate commit: the uniform-weights test required the
  weighted and uniform estimates to differ by more than 1e-5, but they differ by 9.8e-6. The
  bound is now 1e-6, which is still about 10⁵ times the test's 1e-9 relative tolerance, so the
  test still distinguishes the weights.
  Mutation testing then caught 24 of 26 mutants. Two tests were added or strengthened for the
  survivors. First, a fit marked rank-unverified but still carrying an estimate must stay
  `rank-unverified` on the reproduction track. Sol's round 83 survivor ("passed gated targets
  and ignored rank") is caught in both parts. Second, the missing-heading mutant now refreshes
  every receipt's public hash, so only the heading is wrong. All 26 mutants are then caught.

- **2026-11-23, round 84 (final Sol round): NOT READY (6 A, 2 B).** Record:
  `docs/validation/round84-v1.5b-review.md`. Under the review process the owner decides how to
  proceed before any merge. Until then PR #28 is not merged, and no fit is authorized: §10 has no
  `freeze approved` row.
  - **Owner decision (2026-11-23T20:15Z, in chat): "Fix all six, scoped Sol check".** Session S6c
    freezes regression tests for A1–A6, then fixes them per the dispositions. Then one more Sol
    round (round 85) reviews only those six fixes. This round is an owner-authorized exception
    to the two-round cap. PR #28 merges only if round 85 is READY; otherwise the owner decides
    again.

- **2026-11-23, round 84 gates frozen (A1–A6).** These tests xfail while
  `tools/validation/fit_record.py` is absent.
  - **A1.** `run_report` refuses with a `PermissionError`, before it reads or fits anything, when
    the submission is not authorized. It checks against the first-fit log committed in its own
    root, at the runner's clock. Refused cases:
    - no committed ledger;
    - logged in the working copy only;
    - an agent runner;
    - a submission at the freeze instant;
    - a future time;
    - another release.

    The scan requires an output only for a submission in the committed (`HEAD`) log. The commit
    that logs a submission therefore passes, and the next commit needs that submission's
    output. An end-to-end test logs, commits, runs and reruns.

    To test the runner's own check, each synthetic root that is fitted now holds a committed
    synthetic ledger with its logged submissions (`Synthetic.logged`). The runner's clock is
    fixed just after the synthetic submission time.
  - **A2.** The fit-values record declares every cell of the frozen roster on both tracks: an
    estimate and a discrepancy, each as a value or as the cell's pending reason. The roster is
    the condition set of the hash-verified couplings, so the scan reads the couplings through
    the preregistration copy. The record is refused for:
    - an invented condition;
    - any undeclared quantity;
    - both or neither of a value and a reason;
    - an unknown reason;
    - a discrepancy value without an estimate value;
    - an independent estimate declared undocumented;
    - a reproduction track that is only partly pending.
  - **A3.** The scan prints no unexpected file name, even one made only of safe characters, in
    the tier's problems or on the command's output.
  - **A4.** A rank-pending cell, on either track, is declared `rank-unverified` and passes the
    scan.
  - **A5.**
    - An annex entry holds the plan's six fields (procedure 6): frame and convention, geometry,
      vibrational corrections, sample context, numerical comparison, and cause. Each is a
      non-empty text, not all the same, and no two cells share all six.
    - Each receipt links its own Markdown heading. That heading appears once in the public file
      and has a body.
  - **A6.** The record carries each fit's provenance: the versions, the method and each
    condition's fit provenance per track. Each record is also one run of a chain: its run
    number, the SHA-256 of the record it replaced, and the SHA-256 of that run's local report,
    kept as `reports/<dataset>.<run>.md`. The scan refuses a chain where a run's output or
    report was deleted, edited or renumbered.

  Existing tests were amended to the new record format (`_record`, `_reproduced`, the workflow
  tests), to the new annex format (every test that uses `_evidence`), and to the A1 timing (two
  staged-check tests). These now xfail on the round 84 marker.
  No case that the gate rejected before is removed.

- **2026-11-23, round 84 fixes (A1–A6).** The new module `tools/validation/fit_record.py` holds the
  fit-values record's format and checks. Both the writer (`verification.py`) and the scan use it.
  - **A1.** `run_report` checks the submission itself, against the first-fit log committed in its
    root, at the runner's clock (`authorization`). It raises `Unauthorized` (a `PermissionError`)
    before reading or fitting anything. The command now relies on that check. The scan requires
    an output only for each submission in the committed (`HEAD`) log, and still accepts outputs
    bound to a staged submission.
  - **A2, A4.** The record declares every roster cell of both tracks: its estimate and its
    discrepancy, each a value or the cell's pending reason. The roster is the condition set of
    the couplings file, read only when its SHA-256 matches the preregistration copy. A
    rank-pending cell is declared `rank-unverified`, and a pending authors' analysis
    `inputs-undocumented` throughout.
  - **A3.** A file name the scan does not expect is shown as `(a file with an unexpected name)`,
    whatever its characters.
  - **A5.**
    - The annex entry holds the plan's six fields. Each is a non-empty text, not all one text,
      and not another cell's.
    - Each receipt links a Markdown heading that the public file holds once, with a body, and
      that no other receipt links.
    - These checks are structural: the owner's attestation remains the check of substance.
  - **A6.** The record carries the versions, the flags, the method and each condition's fit
    provenance on both tracks. A rerun keeps the record it replaces, unchanged, under
    `retained/`. Each record names:
    - its run number;
    - the SHA-256 of the record it replaced;
    - the SHA-256 of its run's local report, kept as `reports/<dataset>.<run>.md` and never
      overwritten.

    The scan checks the whole chain: numbering, run numbers, predecessor hashes, and each
    report's presence and hash.

  Gate corrections after the gate commit:
  - Four tests built their submission or root without the round 84 setup. Three fitted an
    unlogged submission, and they now use `Synthetic.logged`. One built a root without the
    synthetic roster, and it now uses `_root`.
  - Mutation testing caught 25 of 28 mutants. The three survivors were each masked by another
    check, so three cases were added, one for each check on its own:
    - an invented condition in the declarations only;
    - an unknown reason on an independent discrepancy;
    - couplings changed after the freeze.

    All 28 mutants are then caught.

- **2026-11-23, round 85 (first attempt): no report.** The scoped Sol review of `9ca2803` stopped
  partway: the provider's safety filter flagged the run. It delivered no verdict, so the attempt
  does not count as the authorized round. Its last message named two cases the scan accepted,
  and both were confirmed by reading the code:
  - **A false pending declaration.** A record could declare a real discrepancy as `no-target`.
    That discrepancy then dropped out of the fit tier.
  - **A rollback.** An earlier chain, restored whole, checked out, because nothing tracked in
    git recorded how many runs there had been.

  The orphaned test run was stopped and the reviewer's worktree removed.
  - **Owner decision (2026-11-24T23:15Z, in chat): "Fix both, then rerun 85".** Tests first,
    then fixes for both cases. Round 85 is then rerun as the same scoped review, with a reworded
    brief, and still counts as round 85.

- **2026-11-24, round 85 gates frozen (the two cases).** These tests xfail while
  `fit_record` has no `pending_targets`.
  - **The false pending declaration.** The rules:
    - A cell's discrepancy is pending only for its estimate's own reason or, beside an estimate
      value, for `no-target`.
    - A rank-pending condition is pending for every component.
    - On each track, the `no-target` cells are either every estimated cell (all targets
      withheld: the spot-check is unsigned, P-2) or exactly the estimated cells whose target
      the hash-verified targets file marks pending. Both tracks make the same choice.
  - **The rollback.** A results receipt in §6 now records each dataset's number of fit outputs:
    `fit tier: results (files: benzene-taggar2006 <n>, odcb-chandrakumar1993 <n>)`. The scan
    command prints it (`receipt_status`). The scan then refuses fewer outputs for a dataset
    than the latest receipt recorded. No results row existed before, so no recorded row
    changes.
  - **Amendments.** The synthetic records `_record` and `_reproduced` now give every
    discrepancy, as a signed run with every target present does. The receipt row pattern
    accepts the new results form.

  An o-DCB workflow test covers a pending S_zz target, whose anisotropy waits with its
  discrepancy (`s_zz-target-pending`), and a pending anisotropy target, signed and unsigned. No
  case that the gate rejected before is removed.

- **2026-11-24, round 85 fixes (the two cases).**
  - **False pending declarations.** `fit_record.consistency` checks the pending reasons against
    each other. `fit_record.pending_targets` reads the targets file's pending cells: the file is
    verified against its frozen SHA-256 first, and only its keys and `status` column are read.
    When those cells cannot be read, the record's own problem names it.
  - **Rollback.** `restricted_scan.receipt_status` gives the results status with each dataset's
    number of fit outputs, and the scan command prints it as `receipt: …`. The scan then refuses
    fewer outputs for a dataset than any results receipt in the judged ledger recorded.

  Gate corrections after the gate commit:
  - `_repo` writes stand-ins for the restricted files over two synthetic inputs, so it now binds
    the preregistration copy to those stand-ins again. Four staged-check tests needed that once
    the targets file's hash was read.
  - Mutation testing caught 9 of 11 round 85 mutants. The two survivors (the targets hash not
    checked; unreadable pending cells accepted) were both masked by one test, which replaced the
    targets file with unparseable text. The test now appends a blank line, which keeps the
    parsed content and changes the hash.
  - Rerunning 12 round 84 scan mutants showed three now masked by the round 85 rules: an
    unknown reason, an estimate reason the track cannot have, and an authors' track pending
    only in part. One case was added for each, refused by its own check alone.

  All 11 round 85 mutants and the 12 rerun round 84 mutants are then caught.

- **2026-11-24, round 85 (scoped Sol round, rerun on `a435803`): NOT READY (6 A, 2 B).** Record:
  `docs/validation/round85-v1.5b-review.md`. A1 and A4 are resolved. Still open: A2, A3, A5, A6,
  the false pending declaration and the rollback. Under the review process the owner decides how
  to proceed before any merge. Until then PR #28 is not merged, and no fit is authorized: §10 has
  no `freeze approved` row.

## 7. Exit matrix

One row per exit criterion of the plan's audit table, each with its evidence: a test, or a named
witness with a receipt. `verification.check_exit` (gated in `tests/test_v15_gates.py`) refuses a
missing, repeated or unknown criterion, a result other than `passed` (a CI skip of local
evidence never certifies), an empty reference, and a witness or local-only row without a receipt.

| Exit criterion | Evidence (test or witness) | Local only |
|---|---|---|
| V0.1 selection and rights | `tests/test_v0_corpus.py` (selection and manifest); witness: owner, the staged-scan receipts (§6) | scan: yes |
| V0.2 verified corpus | `tests/test_v0_corpus.py`; witness: owner, both signed spot-check receipts | yes |
| V0.3 frozen criteria and comparison | `tests/test_v0_preregistration.py`, `tests/test_prereg_labels.py`, `tests/test_digitize_figure.py`, `tests/test_v15_gates.py` (amendments, chronology) | digests: yes |
| V1.0 and V1.1 design and fit | `tests/test_core_fixed.py` (including the V1.5a collinear gate), V1.1 benchmark | no |
| V1.2 symmetry and counting | `tests/test_core_symmetry.py`, V1.2 benchmark | no |
| V1.3 application and compatibility | `packages/dipolar-app/tests/test_app_v13_fixed.py` | no |
| V1.4 browser, robot and AI readiness | `packages/dipolar-app/tests/test_app_v14_browser.py`, `web/e2e/fixed-tutorial.spec.ts` (Chromium, Firefox, WebKit) | no |
| Every implemented model has a robot tutorial | `robot.py --scenario tutorial` (rigid), `--scenario fixed-tutorial` (fixed), the V1.5b `jump4` tutorial | no |
| V1.5 honest reporting and no tuning | `tests/test_v15_gates.py` (pages, crosswalk) and V1.5b's `tests/test_v15_verification.py`; witness: Sol review of the discrepancy entries (decision 5B) | annex check: yes |
| Decision 6 and release | witness: owner, the published pre-release, and one external record passing `verification.check_participant` (§8) | yes |

## 8. External evidence checklist

A participant's success claim (decision 2A) is supported only if `verification.check_participant`
finds no problem:

- an opaque participant ID (`P-` and three digits), with no name, handle, e-mail address or
  contact detail in the record (decision 9);
- eligibility under decision 8;
- the candidate's release tag and commit, and the protocol revision;
- a matching SI SHA-256 (decision 10);
- a geometry computed, not copied (guide step 3);
- the owner's signed benzene spot-check receipt (A4);
- all 15 conditions, each with a numerical match under the precision rule below;
- the comparison counts equal to the published counts. Disagreements with the paper do not
  fail a claim.

A record that claims nothing (a failed or incomplete attempt) is kept, not refused.

**The precision rule** (plan, guide step 4). The participant's S_zz must match the owner's
reference within 1e-8 (absolute) when the coordinates have 12 or more decimals. At 8–11 decimals,
the owner's rounding allowance is added: the change in the reference estimate when the reference
coordinates are rounded to the participant's precision in the declared axes. Below 8 decimals,
the participant regenerates the XYZ. The synthetic evidence is
`tests/test_v15_gates.py::test_the_precision_rule_*`: a synthetic axial order on the frozen
geometry, at 8–15 decimals, in the reference axes and turned by 30° about z. It includes a
participant's independent construction (exact multiples of ½ and √3/2) and a refusal of a
geometry 1e-4 Å off. It runs in CI on Linux and Windows and on the owner's macOS.

## 9. Round 82 entries

- **2026-11-22T17:15Z, owner sign-off of the scan receipts (round 82, A6).** The owner approved the
  scans Claude ran on trees `544f718…` (commit `241e8ed`), `55227c7…` (`d5f5aa3`), `be08fce…`
  (`cad9342`) and `46865ee…` (`016a56a`), each passed and not skipped (§6). Later receipts are
  signed the same way, by a value-free approval of the listed trees.
- **2026-11-22, process note (round 82).** Before isolating the suite in a tracked-only copy, the
  round 82 reviewer ran the four-file suite once in the owner's checkout. There, the three
  local-evidence tests read the restricted inputs automatically, to compare them. No restricted
  value appeared in the output, and no experimental fit ran. This is not an exposure in the
  [exposure-log.md](../exposure-log.md) sense (no value was seen), and it is recorded here so that
  it is not repeated: review briefs require a tracked-only copy.
- **2026-11-22, protocol revision (round 82, A7).** P-1 now includes "reviewed", and P-2 its
  checked artifacts and the open-check note. The revision after P-1 is
  `e1116a59be81852bff1fd94dad81bc3fa0cdfcf1f0884f9f921cf6abe046b448`, and after P-2
  `263f26857da15df184c7e662325e39036c307a02bc0042c610d6b8d4dab700b9`, the current revision. The
  §6 revisions `1b12b8f…` and `a27e092…` belong to the round 81 draft, under which no result was
  made.
- **Recording a signed spot-check.** When the owner signs a spot-check receipt, it is appended
  here as a line of its own, `- **Spot-check receipt signed:** `<dataset>`` followed by the
  artifact, its SHA-256 and the UTC time. The page gate reads that line, and until it is present
  the dataset's page must show zero compared cells (P-2).
- **§7 as amended (round 82, A1).** The exit evidence is bound to each criterion, in
  `EXIT_REQUIREMENTS` (`tests/test_v15_gates.py`, which V1.5b's module must equal). Each listed
  test must have passed: not skipped and not xfailed. Each listed receipt must be recorded.

  | Exit criterion | Required tests | Required receipts |
  |---|---|---|
  | V0.1 selection and rights | `tests/test_v0_corpus.py` | staged-index scans |
  | V0.2 verified corpus | `tests/test_v0_corpus.py` | benzene spot-check; ortho-dichlorobenzene spot-check |
  | V0.3 frozen criteria and comparison | `tests/test_v0_preregistration.py`, `tests/test_prereg_labels.py`, `tests/test_digitize_figure.py`, `tests/test_v15_gates.py` | local digests |
  | V1.0 and V1.1 design and fit | `tests/test_core_fixed.py` | — |
  | V1.2 symmetry and counting | `tests/test_core_symmetry.py` | — |
  | V1.3 application and compatibility | `packages/dipolar-app/tests/test_app_v13_fixed.py` | — |
  | V1.4 browser, robot and AI readiness | `packages/dipolar-app/tests/test_app_v14_browser.py`, `web/e2e/fixed-tutorial.spec.ts` | — |
  | Every implemented model has a robot tutorial | `robot --scenario tutorial`, `--scenario fixed-tutorial`, `--scenario jump4-tutorial` | — |
  | V1.5 honest reporting and no tuning | `tests/test_v15_gates.py`, `tests/test_v15_verification.py` | discrepancy review; local annex coverage; restricted-fit scan |
  | Decision 6 and release | `tests/test_v15_gates.py::test_the_release_workflow_uses_exactly_the_approved_trigger` | published pre-release; external record; owner sign-off |

  The release row requires the whole-trigger gate to have passed, so a return to `v*` (which
  only xfails it) fails the exit.
- **§8 as amended (round 82, A1).** The participant check takes **trusted** values from the
  owner, not from the record: the candidate's release tag and commit, the protocol revision, the
  frozen 15-condition roster, the signed benzene receipt, and the published counts, which must be
  complete (all 15 compared, none pending). The record has a closed set of fields at every level.
  A failed or incomplete attempt is checked against that allowlist too, so it cannot carry
  personal data. **Precision rule:** the participant rounds the coordinates **in the input XYZ
  frame**, as written in the XYZ file. The evidence runs the production path
  (`symmetry.validate` with D6h averaging, then `fixed_rows`) on independently built C₆H₆
  geometries, off-centre, with 0° and 30° axes, at 8–15 decimals. The measured miss is below
  8.6e-9 at every precision, below the 1e-8 tolerance with no allowance at all, as the round 82
  bound predicts. The allowance boundary is tested as inclusive. CI results at `016a56a`: Python on
  Linux and on Windows passed.
- **2026-11-22T20:32Z, owner sign-off and merge.** The owner approved the scans of trees
  `bb23b01…` (commit `76f4aba`) and `31cd0fe…` (`1382313`), both passed and not skipped (§6).
  Round 82 was the final review round (NOT READY). Its findings were fixed with gates frozen
  first, without a further review, and the owner decided to merge PR #27 once CI was green
  (all six checks passed at `1382313`; merge `76b4848`).

## 10. First-fit log

Round 83 (A1). This table is the machine-read chronology of the first-fit gate. It is
append-only: a row is never edited or removed, and every later commit's log must extend the
committed one. Rows are in time order (UTC, to the minute). The runner fits only a submission
logged here by its exact fields, after a `freeze approved` row, and only for the owner or a
participant. The restricted-fit scan tier is required from the first `submission` row on. The
§3 rows stay as written. Their first-fit field stays `empty`: a submission is recorded here.

Events: `decisions approved`, `decision changed`, `amendments approved`, `no-fit attestation`,
`freeze approved` (the owner's, once), `submission` (dataset, runner role, release or commit,
protocol revision) and `first access` (the first access to any V1 experimental result, once,
after a submission). The cells an event does not use hold `—`.

| UTC | Event | Dataset | Runner | Release or commit | Protocol revision |
|---|---|---|---|---|---|
| 2026-11-21T14:59Z | decisions approved | — | — | — | — |
| 2026-11-21T15:32Z | amendments approved | — | — | — | — |
| 2026-11-21T15:33Z | decision changed | — | — | — | — |
| 2026-11-22T14:11Z | no-fit attestation | — | — | — | — |

The first four rows transcribe §1, §3 and the §6 entries of those times: the decisions, P-1 and
P-2, decision 11's change from A to B, and the owner's signed attestation.
