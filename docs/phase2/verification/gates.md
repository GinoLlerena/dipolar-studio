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
