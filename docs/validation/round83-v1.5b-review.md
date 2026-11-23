# Round 83: V1.5b report workflow, fit tier and jump4 tutorial (GPT-6.2-Sol)

Independent review of PR #28 at `b413038` (`git diff 5b219c4..b413038`) by GPT-6.2-Sol (Codex,
reasoning effort high), 2026-11-23. The review used a tracked-only worktree at that commit.
Verdict: **NOT READY** (6 A, 2 B). The report is below, as delivered. The orchestrator's
provisional dispositions follow it. Each finding is verified before its fix, and each fix is
preceded by a frozen regression test.

## Report

### Class A — blocks merge

1. **The first-fit gate lacks an enforceable, append-only transition.** A synthetic probe reached
   the fit boundary with a submission attributed to an agent and dated before approval. The runner
   validates the submission's shape without checking the freeze or owner authorization. The
   scanner looks for the original §3 row anywhere in the file, and the test pins that row to
   `empty`. If the owner appends the first-fit entry and the local outputs are later deleted, the
   scanner can report `pre-result`. Require a structured append-only chronology, verify the
   authorized submission against it before fitting, and check the staged ledger when issuing a
   staged-tree receipt. `tools/validation/verification.py:718`, `tools/validation/verification.py:778`,
   `tools/datasets/restricted_scan.py:260`, `tools/datasets/restricted_scan.py:320`,
   `tests/test_v15_fit_tier.py:151`, `docs/phase2/verification/gates.md:3`
2. **The fit tier can pass with missing results.** A synthetic probe logged benzene and supplied
   only an ODCB file with one invented cell and a blank revision. The scanner returned `results`
   with zero problems. Deleting one dataset's file while another remains can likewise leave a
   passing scan, and a rerun overwrites the previous file for that dataset. Bind required files to
   retained submissions and protocol revisions, validate exact cell and quantity coverage, and
   retain each result across reruns. `tools/datasets/restricted_scan.py:280`,
   `tools/datasets/restricted_scan.py:325`, `tools/validation/verification.py:983`
3. **Restricted output can escape through paths and diagnostics.** A synthetic probe made the local
   output root a symlink to a shared directory. `write_local` wrote into that directory because
   containment was checked against the resolved symlink target. Both writers use that guard. A
   second probe placed a number in an unknown fit-record key and observed it in scan CLI stdout.
   Anchor writes to the checkout's actual local directory, use atomic replacement to avoid
   overwriting linked files, and report malformed records using fixed messages and entry
   locations. Sanitize unexpected filenames before printing them.
   `tools/validation/verification.py:896`, `:954`, `:986`; `tools/datasets/restricted_scan.py:289`,
   `:328`, `:363`
4. **The report cannot run a reproduction comparison or apply P-2 distinctly to that track.** The
   runner hard-codes `mode="pending"` and `target=None`. An open spot-check and an unverified rank
   both yield `inputs-undocumented` on that track. Even if method evidence becomes available, the
   report has no path to use it, preserve the printed table token, or report a fallback attempt.
   Wire owner-local method evidence, estimates and target precision into the report. Freeze a
   synthetic end-to-end case for reproduction and fallback, including P-2 and rank precedence.
   `tools/validation/verification.py:469`, `:807`; `tools/validation/prereg_labels.py:197`;
   `tests/test_v15_verification.py:648`; `docs/phase2/v1.5-plan.md:132`
5. **Matching keys can stand in for completed discrepancy reviews.** Copying the expected keys into
   both lists produces `explained discrepancy` even when there is no numeric annex or reviewed
   public entry. The positive test constructs exactly that evidence. Require locally verifiable
   references to the annex and reviewed public entry, bound to the dataset, track, cell and
   protocol revision. Keep the failure unresolved when either reference is missing or stale.
   `tools/validation/verification.py:697`, `:800`; `tests/test_v15_verification.py:935`;
   `docs/phase2/v1.5-plan.md:134`
6. **The runner skips protocol validation and drops fit provenance.** A changed frame or invalid
   protocol can reach the fit if the submission carries its recomputed hash. After the fit, the
   local report retains numerical diagnostics but drops the fitted model, frame, science identity,
   versions and mixture flags. Validate the closed schema and `prereg.validate` before fitting,
   and retain those fields in the local report. `tools/validation/verification.py:775`, `:791`,
   `:837`; `docs/phase2/v1.5-plan.md:124`

### Class B — document, do not block

- **The receipt-format gate passes vacuously at this head.** The cutoff is appropriate for the
  first fit-tier receipt, but no §6 row reaches it yet, and the test ignores the head commit
  message. Moving the cutoff to 2099 also passes. Test the first applicable receipt explicitly and
  reject malformed receipt rows. The four commit messages matched their tree and UTC receipts,
  each prior receipt appeared in the next commit, and the PR's ledger changes were additive. The
  `b413038` row is pending as planned. `tests/test_v15_fit_tier.py:358`,
  `tools/datasets/restricted_scan.py:216`, `docs/phase2/verification/gates.md:117`
- **The jump4 tutorial demonstrates acceptance by credential.** The server rejects approval from
  the robot and agent principals, and the tutorial verifies whole acceptance by the user principal
  before waiting for the job and fetching `run.get`. The same ready file also contains the human
  credential, so a process with that file has access to it. Document that boundary or supply the
  robot with a credential file limited to its roles. The rejection and timeout tests passed, and
  the synthetic fixture uses an explicit four-conformer reference independent of the engine.
  `tools/robot/robot.py:584`, `:638`; `packages/dipolar-app/src/dipolar_app/cli.py:218`;
  `packages/dipolar-app/src/dipolar_app/policy.py:59`; `datasets/biphenyl-synthetic/jump4_tutorial.py:37`

### Readings and evidence

- **(a) Accept `pending`.** Documented geometry, objective and weights with undocumented
  corrections qualify for neither reproduction nor the frozen fallback.
- **(b) Accept the chlorine omission.** Six carbons and four protons specify the declared H–H
  geometry and C₂v frame. The axes, covariance reconstruction and conversion, and both margin
  formulas match the frozen procedure.
- **Checks.** Verification and scan suite: 370 passed, 3 skipped, 1 expected xfail. Jump4 and M2
  suite: 9 passed. Ruff and mypy passed.
- **In-memory mutations.** Ignored hash mismatches — caught. Dropped covariance cross terms —
  caught. Omitted receipt coverage — caught. Made the reproduction boundary exclusive — caught.
  Dropped truncation — caught. Moved the receipt cutoff into the future — survived. Passed gated
  targets and ignored rank in the reproduction track — survived. Omitted the full jump4 result —
  caught.

The detached worktree was removed. All fit tests used synthetic fixtures. A raw commit metadata
read displayed a contact field in tool output, breaching the review's output rule.

## Dispositions (provisional; each finding is verified before its fix)

| Finding | Disposition |
|---|---|
| A1 first-fit transition | **Accept.** Replace the single §3 row with a structured, append-only first-fit log. The runner refuses to fit unless the submission matches a logged, authorized entry after the frozen approval (`freeze_ok`). The scanner reads the ledger from git's index, so the staged receipt binds the staged ledger. |
| A2 missing results | **Accept.** Each logged submission requires a retained local fit output for its dataset and protocol revision, with exact roster coverage of cells and quantities. Reruns write new files and never overwrite earlier ones. |
| A3 escape paths | **Accept.** Refuse any symlink along the local output path, write atomically without following links, and print fixed, value-free messages (no key names or raw file names). |
| A4 reproduction track | **Accept.** Wire an owner-local method-evidence record (the documented inputs, the authors' estimates, the printed table tokens or figure precision) into `run_report`, with P-2 gating and rank precedence on that track. Freeze a synthetic end-to-end case for reproduction and fallback. |
| A5 review evidence | **Accept.** A review counts only with local references (path and SHA-256) to an existing annex entry and an existing reviewed public entry, each bound to the dataset, track, cell and protocol revision. A missing or stale reference keeps the failure unresolved. |
| A6 protocol validation and provenance | **Accept.** Run the closed-schema check and `prereg.validate` before any fit, and keep the model, frame, science identity, versions and mixture flags in the local report. |
| B1 vacuous receipt gate | **Fix.** This commit appends the first applicable row (`da39310`). Pin that row in the test and reject malformed receipt rows. |
| B2 credential boundary | **Document.** The ready file holds every principal's credential. The tutorial states this, and the robot reads only its own and the agent's. |
| Readings (a), (b) | Accepted by the reviewer; no change. |
| Output-rule breach | Recorded. The contact field appeared only in the reviewer's local tool output, not in any external request or tracked file. Future briefs say not to print raw commit metadata. |

## Corrections

- The `b413038` commit message says "Mutation: 22 of 23 caught". The true figure is 19 of 23
  caught. Three mutants are equivalent by construction (half-even rounding, exact-binary rounding,
  the 3-digit tier applied everywhere). One survives: a missing ledger is counted `pre-result`,
  although its problem still fails the check.
