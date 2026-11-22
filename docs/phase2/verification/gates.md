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
| No-fit attestation for V1.5 work | **Signed by the owner, 2026-11-22T14:11Z:** "No V1 fit of experimental data has been run by anyone for V1.5 before this entry." Exposure checked against [exposure-log.md](../exposure-log.md) (last entry 2026-11-19: no V1 fit). |
| Decisions approved | 2026-11-21T14:59Z (§1) |
| V0.3 amendments P-1, P-2 approved | 2026-11-21T15:32Z (§2) |
| V1.5a gates frozen | pending |
| First experimental fit submission (UTC, release or commit, protocol revision, dataset, runner role) | empty |
| First access to any V1 experimental result (UTC) | empty |

Until the V1.5a gates are frozen, only synthetic data (the D6h rehearsal and the existing
synthetic datasets) is fitted, by the owner, by every agent and by any participant.

## 4. Owner actions outstanding

- Sign the receipt of each staged-index scan (decision 11, as changed in §6).
- Sign the benzene and ortho-dichlorobenzene spot-checks (`SPOT-CHECK.md` under
  `datasets-local/`). The benzene one gates V1.5e.
- Publish the `v0.1.0b1` draft before the 8CB testers start (decision 7).
- Recruit one benzene participant and two 8CB testers (decision 8).

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
