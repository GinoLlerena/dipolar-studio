# Validation rounds 73–74: V0.3, the preregistration

Reviewer: GPT-6.2-Sol (Codex, reasoning effort high), independent of the author. The medium plan
allows at most two rounds. Class (A) findings block; class (B) findings are documented.

The step is [`docs/phase2/v0.3-preregistration.md`](../phase2/v0.3-preregistration.md) and its JSON
and schema. It also covers the two target tools (`tools/datasets/digitize_figure.py`,
`tools/datasets/taggar2006_targets.py`), the label rules (`tools/validation/prereg_labels.py`) and
their tests. No experimental value was fitted by V1 in this step.

## Round 73 (on 62feaae): NOT READY, 4 A + 4 B

**The reviewer confirmed:**
- both target tools reproduce their recorded SHA-256 and the local files byte for byte;
- 10 Fig. 3 markers, read independently from the raw crops (all four overlap-resolved ones
  among them), each match a unique condition within the declared precision;
- three Fig. 2a readings agree;
- the 15 benzene target keys match the SI;
- the signs, the pair orbits and the ortho-dichlorobenzene conversion are right;
- the cyclic map is right-handed.

**The reviewer viewed:** Chandrakumar & Burnell's Tables I–II and Figs. 1–3 (with the raw crops,
the overlays and the local couplings and targets), and Taggar et al. pp. 1364–1365 with the
benzene targets and the SI. This is recorded in the exposure log.

**Freeze order.**
1. The new tests and their targets were committed first, in `40beabc`. On the round-73 code, 12
   of them failed, and the label tests could not be collected because their module did not exist
   yet.
2. Two frozen targets turned out to be mutually inconsistent, and were corrected in their own
   commit (`5be66ed`), still before any fix:
   - the label test's synthetic values coincided at four decimals with a restricted value, so the
     frozen scan flagged the frozen test itself. They moved to magnitudes no dataset has; the
     criterion's arithmetic is unchanged;
   - the scan now skips generated dependency locks, where a timestamp matched.
3. The fixes came after both. The fix commit adds one test, which checks the label module's
   constants against the JSON. It changes no frozen test.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | The dataset label could overstate coverage: one agreement with many pending cells was "supported". Eligibility (unverified rank, a missing S_zz target for the anisotropy), mixed reviewed and unreviewed disagreements, and the drop-one reporting were undefined. | A frozen roster (15 and 44 cells), enforced by the label function. Eligibility, in order: rank-unverified, no-target, s_zz-target-pending. The precedence is: unresolved failure, explained discrepancy, pending, **partially supported**, experimentally supported (every cell compared and agreeing). Counts are given with every label. The full-data label is primary, and the drop-one labels are reported with their counts. Code: `tools/validation/prereg_labels.py`; tests: `tests/test_prereg_labels.py`. |
| 2 | A | The reproduction and amendment rules allowed outcome-dependent choices. The JSON gated only on geometry, the 1/σ² fallback defined only its failure label, and "before the affected fit" allowed revision after an initial result. | A reproduction claim requires documented geometry, objective, weights and corrections. The fallback is labelled "approximate reproduction (assumed weights 1/σ²)" for either outcome. The original protocol and its results are kept. Amendments record their date, kind, reason, evidence and before/after hashes (in the schema). Anything after **any** V1 experimental result is post hoc. V0.1 and V0.2 now say that their pending gate is the reproduction comparison. |
| 3 | A | Fig. 3 assignment was by rank, with the temperature check only printed. Keys shifted in memory left 11 wrong rows marked as targets. | Assignment by a frozen tolerance: a unique marker within 0.0015 of T/T_NI, matching no other condition. Otherwise the cell is pending (`no-marker`, `ambiguous`), and rank is not used. The V0.2 transcription's SHA-256 is verified. Fig. 2 outcomes are explicit: agrees 18, disagrees 0, unavailable 24, ambiguous 2. The switch to Fig. 3 as primary is recorded in V0.3 §5 and V0.1. Tests: synthetic Fig. 3 and Fig. 2 pages, end to end, covering correct, wrongly keyed, missing marker, disagreement, unavailability and an unrecorded transcription. |
| 4 | A | An ACS value was tracked: the benzene README gave the paper's S_zz for run 1, 1.31 mol %, and a distance derived from it. The guard scanned only the JSON, and could be bypassed. | The scale check moved to the local target record. The README keeps only the SI ratios. The derived distance is gone from the preregistration and from a test fixture. The JSON is validated by a closed schema: typed fields, constants, 64-hex hashes, path patterns. A local-only test scans every tracked file for restricted cells and reports path:line. It uses four or more significant digits everywhere, and 3-decimal targets in the Phase 2 and validation docs. Three pre-existing coincidences are allowlisted by token hash, and only in files that predate the exposure. The README token remains in `main`'s history, an owner decision (V0.3 §10). |
| 5 | B | The 5 % threshold: defensible, but no bound for the substituted ring. The anisotropy margin is an axial-scale heuristic. | V0.3 §6 says both. Signed discrepancies are shown with their margins, and agreement is described as consistency between two analyses of the same couplings. |
| 6 | B | Record D-4's benzene x ∥ C2′, the paper's apparent axial-relation reversal, and how paper-frame errors are formed. | V0.3 §3–§4. Paper-frame standard errors use the full covariance, transformed by the conversion matrix (also in the JSON). |
| 7 | B | The precision is a resolution estimate. Document h/6, the split pixel and the Fig. 2 rule. Use the lock. Test missing and misassigned markers end to end. | V0.3 §5 and the tool's docstring. A locked `datasets` dependency group (`uv run --group datasets`). The end-to-end tests are in row 3. |
| 8 | B | The benzene readings are two implementations of one text layer. The frame test hard-coded the conversion, and survived an inverted JSON conversion and swapped orbits. | Said in V0.3 §4 and the tool; the rendered-page spot-check is kept. The test builds the axes from the geometry and the orbits from the symmetry operations, then checks the JSON's map, orbit keys and conversion matrix, and the signs of the couplings. **Mutants:** an inverted conversion, swapped orbits, a loose match tolerance, and "partially" relabelled as "supported". All four fail the tests. |

## Round 74 (on 320bf9a): NOT READY, 5 A + 3 B — the final round

**The reviewer confirmed:**
- both tools reproduce the JSON's SHA-256 under the locked group;
- all 44 condition/component keys match an independent reading of the raw Fig. 3 crops;
- the assignment uses the tolerance without rank, and an unrecorded transcription is refused;
- the Fig. 2 outcomes (18 / 0 / 24 / 2) are reproduced;
- the four round-73 mutants fail;
- the freeze order holds: `40beabc`, then the corrections in `5be66ed` (judged legitimate), then
  `320bf9a`.

**The reviewer viewed:** the local ortho-dichlorobenzene couplings and targets, both Fig. 3
panels, and the 15 benzene targets (exposure log).

Round 74 was the last round allowed by the medium plan. Its findings were fixed and are documented
here without another review.

**Freeze order.**
1. The new tests were committed first, in `2c0e788`. Four preregistration tests failed on the
   round-74 code, and the label and scan tests could not be collected because their modules did
   not exist.
2. The round-73 scan test was replaced by the stronger one in that commit.
3. One frozen target was corrected in its own commit (`62d878e`), before any fix. The new exact
   orbit-alias check applies to the ortho-dichlorobenzene keys, which list every alias as printed
   (D12=D34). The benzene SI's labels name one pair per orbit, so for benzene the check stays
   "in the orbit".
4. The fixes came after both.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | The labeler accepted a caller-supplied roster, an empty drop list, and unknown statuses. The schema allowed an empty sensitivity object. | `tools/validation/prereg.py`. `frozen_roster` reads the condition keys from the couplings file after verifying its SHA-256. `dataset_report` refuses cells that do not cover that roster, always adds the frozen drop-one labels, and records the protocol revision. `Cell` refuses unknown statuses. `sensitivity` refuses an empty or foreign drop list. Full support requires agreeing = roster. The schema requires the sensitivity list as a constant. |
| 2 | A | The amendment rule asked the JSON for its own hash, and the schema accepted a data correction without evidence or hashes. | The protocol revision is the SHA-256 of the canonical JSON without the amendment ledger (`protocol_sha256`). Ledger entries name the revisions before and after. Data and target corrections must give their evidence, artifact path and artifact hashes (the schema's if/then). Each report records its revision. |
| 3 | A | The scan missed trailing zeros, a leading point, scientific notation, UTF-16 and the colon form. Exceptions were file-wide, and the whole lock file was skipped. | `tools/datasets/restricted_scan.py`. It scans the index blobs, decodes them, and parses every numeric literal by value. Its exceptions are six single lines by hash, each verified in the last commit before 2026-11-18, plus the `upload-time` fields of `uv.lock`. Hits are reported as path:line only. The limits are documented (V0.3 §11). Synthetic tests: `tests/test_restricted_scan.py`. |
| 4 | A | The schema accepted a malformed conversion, duplicate estimands, a changed roster and a path out of `datasets-local`. | Each dataset's definition is pinned as constants in the schema: counts, estimands, orbits, frame map, conversion, roster, flags, and the input and target paths. Only hashes and the pending count vary. A cross-field validator (`prereg.validate`) checks the invariants: roster = conditions × estimands, a square conversion, a rotation as frame map, ν = N − d, and contained paths. |
| 5 | A | A shared report could disclose restricted targets by subtraction (fit minus signed discrepancy). | V0.3 §6 says what stays local and what is shared. Per-cell targets, fits of restricted cells, discrepancies and margins stay in `datasets-local/`. What is shared is `prereg.shareable`: labels, counts, drop-one labels and the protocol revision. The proposal's V1.5 page is updated to match. |
| 6 | B | Reproduction details. V0.1 still pointed to the tracked README. | The V0.1 pointer now leads to the local record. The fallback objective is spelled out (WLS with 1/σ², the authors' geometry, no correction unless documented). |
| 7 | B | Orbit aliases could be truncated. Paper-frame errors needed the basis conversion. | Exact alias sets for ortho-dichlorobenzene, and the orbit keys checked against the coupling files. V0.3 §3 gives Σ_ac = J Σ_b J with J = diag(1/√(3/2), √2), then M Σ_ac Mᵀ. |
| 8 | B | The replay should fail if the lock changes. | `uv run --locked --group datasets …` in V0.3 §9 and the tools' docstrings. |

**Mutation checks.** These changes fail the tests:
- an inverted conversion, swapped orbits, a loose match tolerance, "partially" relabelled as
  "supported" (round 73);
- an empty drop list, a reduced roster, an unknown status, a traversal path, a truncated alias;
- each evasion form of the scan.
