# Round 81: V1.5a gate freeze (GPT-6.2-Sol)

Independent review of PR #27 at `d5f5aa3` (`git diff 57307e9..d5f5aa3`) by GPT-6.2-Sol (Codex,
reasoning effort high), 2026-11-22. Verdict: **NOT READY** (7 A, 1 B). The report is below,
as delivered. The orchestrator's dispositions follow it.

## Report

The candidate leaves required gates unfrozen, and several frozen tests accept defects they are
meant to catch. The requested suite finished with **90 passed, 37 xfailed, 3 skipped**.

### A — Blocks merge

1. **The V1.5a ledger is incomplete.** The plan requires an exit matrix with a test or named
   witness for each gate, an external evidence checklist, and tests for missing or skipped
   evidence and unsupported success claims. It also explicitly requires synthetic and
   cross-platform evidence for the participant precision rule. The ledger defers the exit tests
   and has no precision evidence. Freeze those items in V1.5a. The plan assigns runner-level
   roster, receipt, gated-target and restricted-fit scan tests to V1.5b, so those can stay there.
   (`docs/phase2/v1.5-plan.md:65`, `:178`; `docs/phase2/verification/gates.md:81`)
2. **The chronology tests can approve a fit while the freeze is open.** `freeze_ok` receives
   decision dates, one amendment timestamp and dataset/timestamp pairs. It never receives the
   freeze approval, which the ledger still marks pending. An in-memory implementation passed every
   chronology case while accepting a submission in that state. Require the dated freeze approval
   and complete decision and amendment records. Add refusals for a missing approval, a submission
   at the freeze instant, a missing decision key, and missing access time after submission.
   Exercise the earliest failed or successful submission across datasets and runner roles.
   (`tests/test_v15_gates.py:100`; `gates.md:59`; `v1.5-plan.md:31`)
3. **The V1.5b xfails mask implementation bugs, and the page gate can accept malformed output.**
   An internal `AttributeError` in an existing crosswalk left all ten crosswalk cases xfailed.
   The page regex accepted a valid field beside a malformed duplicate and accepted a field inside
   a code fence. Restrict xfail to the exact missing module or page and let exceptions from
   implemented code fail. Add both page mutations and assert that experimental pages render the
   original V0.3 label and counts alongside the mapped status. (`tests/test_v15_gates.py:27`,
   `:70`; `v1.5-plan.md:98`)
4. **The collinear test checks the shape of the null basis but accepts four zero columns.**
   Replacing `null_b` with zeros in memory passed both cases. The expected couplings are
   independent of `fixed.py`, but the recovered projection is decoded with the production
   `matrix_from_b`. Use the documented basis to build an independent contraction oracle, check
   that the four null columns are orthonormal and annihilate the observable, and rotate the same
   axis-aligned fixture into the second frame. The current rotated case changes the line's
   orientation relative to the tensor before rotating both. (`tests/test_core_fixed.py:762`;
   `docs/phase2/v1.0-design.md:279`; `v1.5-plan.md:71`)
5. **The release guard can admit an extra route and still pass every tag case.** Adding `v9*` to
   the three approved patterns passed all sampled cases and admitted `v9.9-not-a-package`. The
   reader also rejects GitHub's documented backslash escape for a literal `+`. Pin the approved
   package-only filter list when V1.5c lands and keep the positive and negative cases. If the
   reader keeps accepting other syntax, handle documented escapes or reject unsupported syntax
   explicitly. (`tests/test_v15_gates.py:159`; `v1.5-plan.md:211`)
6. **The candidate lacks an exact-tree scan receipt, and the ledger was edited in place.** The
   recorded tree matches `241e8ed`. The tree for `d5f5aa3` is `55227c7…`, with no matching receipt
   in the reviewed diff. The second commit also replaced the attestation row and removed an
   outstanding action despite the append-only rule. Append dated attestation and completion
   entries. Have the authorized operator scan the exact candidate index and bind the signed
   receipt to its `git write-tree` outside that same tree, then append the historical pointer.
   (`gates.md:3`, `:59`, `:95`)
7. **The protocol hash identifies two different reporting policies.** Both entries satisfy the
   schema and use the exact §8 hash formula. Because that formula excludes the amendment ledger,
   a report under the old policy and one applying P-2's target suppression carry the same
   revision. Add closed JSON fields for the P-1 disclosure and P-2 gating policies, bind the
   runner to those fields, and record the before and after hashes for each amendment. Keep the
   original revision in history. (`v0.3-preregistration.md:258`; `tools/validation/prereg.py:35`;
   `v0.3-preregistration.json:5`)

### B — Document

- Add the dated decision 6 pointers the plan requires: both the proposal and the status page
  still list external reproduction as open. Record the P-1 rights check before publishing cell
  identities, and refer to ineligible people by role in the ledger (decision 8 currently names
  public academic names). (`v1.5-plan.md:10`; `docs/phase2-proposal.md:23`;
  `docs/STATUS.md:400`; `gates.md:25`)

### Verified

- P-2 records per-dataset, hash-bound spot-check gating for both tracks, `rank-unverified`
  precedence and the ODCB note. Decision 4's mapping, the reviewed annotation and the five
  initial page statuses match the plan.
- The chronology tests cover equality at amendment approval, an earlier submission listed second,
  the known interval between submission and access, and the explicit unknown-access case. The
  recorded amendment approvals precede the attested first-fit cutoff. Both amendments are
  schema-valid, and V0.3 §§6–7 match the baseline byte for byte.
- Both collinear cases passed an isolated rerun. They assert rank 1 of 5, the 1e-10 contraction
  and 1e-8 Hz prediction tolerances, and five unverified component estimates. All 37 strict
  markers produced `XPASS(strict)` with in-memory implementations satisfying their current
  assertions. The three proposed package patterns agree with GitHub's documented syntax for the
  sampled tags.
- `git diff --check 57307e9..d5f5aa3`, the ledger compared against `241e8ed`, both commit trees
  checked, and the four test files run from a tracked-only copy. The three skips were local-evidence
  checks, including the restricted-value scan. No disclosure in the public ledger. The repository
  was unchanged.

## Dispositions (orchestrator)

All seven A findings are accepted, with one correction on A6. The B finding is accepted.

- **A6:** the receipt for tree `55227c7` exists, but only in commit `d5f5aa3`'s message (the
  receipt cannot sit inside the tree it describes). The in-place edit of the attestation row and
  the removed action are real breaches of the append-only rule. Fix: restore the original
  rows, append dated entries, and add the `55227c7` row to §6.
- **A7:** this reverses the earlier choice to leave the protocol hash unchanged, which the gate
  ledger had left open for review. Closed JSON fields for P-1 and P-2 will change the protocol
  revision. Both amendment entries will record their before and after hashes.
- Each fix is preceded by a regression test that fails on the current candidate, as in rounds
  77–80.

## Fixes

The regression gates are in commit `cad9342`, before the fixes, and the fixes follow it.

| Finding | Gate (`cad9342`) | Fix |
|---|---|---|
| A1 | Exit matrix, external evidence checklist and precision-rule tests in `tests/test_v15_gates.py` | Ledger §7 (exit matrix) and §8 (checklist and precision rule). The precision tests pass now, on every CI platform. |
| A2 | `freeze_ok(ledger)` and `classify_amendment(made, ledger)` on the whole ledger, with 12 refusals | Implementation in V1.5b. The gates run as soon as `verification.py` exists. |
| A3 | The xfail applies only while `verification.py` is missing. Pages are read outside fences, with exactly one valid field and consistent V0.3 label counts. Six page mutants. | As A2. Three loose implementations each fail. |
| A4 | Collinear gate: an independent D-7 decoder, null directions orthonormal and annihilating the observable, the same fixture rotated | Test only: the fitter was already correct. Seven mutants are caught, including all-zero null directions. |
| A5 | The workflow's filters must be exactly the approved list. The reader handles `\` escapes and refuses unsupported syntax. | The guard itself lands in V1.5c, as planned. |
| A6 | (ledger) | The §3 row and §4 action are restored to their `241e8ed` text. The signature is a new §6 entry, and the `d5f5aa3` and `cad9342` scan rows are appended. |
| A7 | Closed `reporting` fields, the hash chain, the schema, and `prereg.spot_check_gate` | JSON `reporting.disclosure` (P-1) and `reporting.spot_check_gating` (P-2). The schema requires both as constants. The revision goes 332be1d… → 1b12b8f… → a27e092…, and §8 records the chain. The runner applies P-2 through `prereg.spot_check_gate`. |
| B | — | Dated pointers in `docs/phase2-proposal.md` and `docs/STATUS.md`. A rights-check action for P-1 in ledger §4. Decision 8 by role (§6). |

# Round 82: re-review (GPT-6.2-Sol)

Fresh independent review of PR #27 at `016a56a`, 2026-11-22. This was the final round. Verdict:
**NOT READY** (8 A, 1 B resolved). Summarized from the report. Each finding was demonstrated
with scratch implementations outside the repository.

## A — Blocks merge

1. **A1: exit and participant evidence can be self-certified.** A `check_exit` that passed every
   assertion accepted all-CI rows with placeholder references and no local receipts. A
   `check_participant` accepted a bogus commit and revision, 15 unrelated condition keys,
   matching counts with all 15 comparisons pending, nested personal fields, and personal fields
   on failed attempts. *Fix:* bind the evidence each criterion requires to that criterion.
   Validate participants against trusted release and protocol identifiers, the exact roster, the
   signed benzene receipt and independently supplied completed counts. Apply a closed field
   allowlist at every level, failed attempts included.
2. **A1: the precision tests bypass the participant's geometry processing.** All acceptance
   cases pass with a zero allowance, and at 30° the participant and owner use the same array. In
   a synthetic rounding-tie case the raw-row fit missed by 1.18e-8, but the production D6h
   averaging reduced it to 1.48e-9. For a centred planar ring rounded at 8 decimals, the axial
   error is below 8.6e-9 for |Szz| ≤ 1, so the rule is defensible in that domain. *Fix:* freeze
   evidence with independently built C/H geometries through `symmetry.validate` and
   `fixed_rows`. Specify rounding in the input XYZ frame. Test the allowance boundary directly,
   and record the platform results.
3. **A2: the chronology gates can still certify a late amendment.** A `freeze_ok` that passed
   every case accepted an unsigned no-fit attestation and a P-2 approval after the first
   submission. A classifier using `submissions[0]` passed every classification case. *Fix:*
   require the dated attestation and complete submission provenance. Add late and missing
   amendment-approval cases, and unordered submissions in both APIs.
4. **A3: contradictory experimental pages pass.** A page reporting a V0.3 label of `pending`
   with a fully compared, fully agreeing roster passed, and so did a page missing its V0.3 line.
   *Fix:* exactly one visible V0.3 line, its label validated against its counts, zero compared
   cells on the initial pages while P-2 is unsigned, all tested through `check_page`. The
   import exemption should depend on the module file being absent: an import error that names
   `verification` still xfails.
5. **A5: other trigger routes stay open.** Adding `push.branches: [main]` or `on.create` passed
   with the approved tag list intact. *Fix:* freeze the whole event mapping, and make V1.5c's
   exit fail on a return to `v*`.
6. **A6: the owner's sign-off on the scan receipts is missing.** The reviewer rebuilt all four
   trees and matched them to the commit-message receipts. The plan also requires the owner to
   sign them. *Fix:* reference the owner's value-free approval of those exact trees.
7. **A7: P-2's helper diverges from target withholding, and P-1's review condition is outside
   the hash.** With no receipt, an anisotropy cell stayed `s_zz-target-pending` where `target=None`
   gives `no-target`. Equal empty digests opened the gate. P-1 authorizes *reviewed* entries
   only, but the hashed fields omit that condition. *Fix:* bind the receipt to the dataset and the
   frozen artifact digest. Withhold targets before classification in both tracks. Encode
   "reviewed" in the policy, regenerate the hashes, and assert the ODCB open-check note.
8. **Candidate CI is red.** The WebKit preview-domain test failed (152 other browser cases
   passed). *Fix:* rerun it alone at this SHA, compare it with the baseline, and record green
   checks before merge.

## B

Resolved. Keep future eligibility records role-only, and record the per-dataset rights check
before publishing any cell identity.

## Verified

A4 is resolved. The hash chain 332be1d → 1b12b8f → a27e092 reproduces. The schema rejects extra
keys at every reporting level, the other JSON fields are unchanged, and §§6–7 match byte for
byte. The four-file suite in a tracked-only copy: 121 passed, 70 xfailed, 3 skipped.

**Process note.** Before isolating the suite, the reviewer ran it once in the original checkout,
where the three local-evidence tests read the restricted inputs automatically. No restricted
value appeared in the output, and no experimental fit ran. Recorded in the gate ledger.

## Round 82 fixes

The regression gates are in commit `76f4aba`, before the fixes. Round 82 was the last review
round, so these fixes have had no independent review, and the merge is the owner's decision.

| Finding | Gate (`76f4aba`) | Fix |
|---|---|---|
| A1 exit | `EXIT_REQUIREMENTS` per criterion, and 12 refusals (placeholders, all-CI, skipped or xfailed, missing receipts, unknown fields) | Ledger §9 (§7 as amended). Implementation in V1.5b. |
| A1 participant | Trusted owner values, a closed allowlist at every level (failed attempts included), and 15 + 10 refusals | Ledger §9 (§8 as amended). Implementation in V1.5b. |
| A1 precision | The production symmetry path, independent C₆H₆ geometries, an off-centre input frame, 0° and 30° axes, the measured miss below 8.6e-9, an inclusive boundary | Passes now. Ledger §9 states that rounding happens in the input XYZ frame. |
| A2 | The attestation, submission provenance, late or missing amendment approvals, unordered submissions (22 refusals, 10 classifications) | Implementation in V1.5b. |
| A3 | The xfail applies only while the module file is absent. Exactly one V0.3 line, the label consistent with the counts, zero compared cells while P-2 is unsigned | Implementation in V1.5b. Ledger §9 sets the format of the signed-receipt line. |
| A5 | The whole `on:` mapping, and five other-route refusals | The guard lands in V1.5c. The exit row requires the gate to have *passed*. |
| A6 | — | Ledger §9: the owner's sign-off of the four trees (2026-11-22T17:15Z), and the `016a56a` and `76f4aba` scan rows in §6. |
| A7 | "Reviewed", the checked artifacts and the open-check note in the closed fields; the gated classification; the notes | JSON and schema. `prereg.spot_check_signed`, `classify_gated` and `label_notes` replace `spot_check_gate`. The revision goes 332be1d… → e1116a5… → 263f268…, and §8 explains the superseded round 81 hashes. |
| CI | — | The WebKit failure did not repeat on rerun (all six checks green at `016a56a`). |

Evidence: a scratch reference implementation passes every gate. Five loose versions, built as
round 82 described, each fail.
