# Validation rounds 61–62: beta step B4 (beta readiness)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

The beta release's steps are in [round55-beta-b1.md](round55-beta-b1.md). B4 makes the beta
ready to hand to testers. **Publishing the release and recruiting the testers are the owner's**;
the beta's exit (03 §8) is two or more external users reproducing the 8CB dataset on their own,
with no open S1 issue.

## What step B4 delivers

- **The testers' guide** (`docs/beta/testers.md`): install and a first check; **the exercise**,
  reproducing biphenyl in 8CB from the tester's own transcription of Di Pietro (2013), Table 3.1
  at T_red = 0.930 (pages, columns, signs, σ, the thesis-label → pair table), fitted in notebook 3
  or in the app (the clicks, with σ = 1 for the unweighted configuration), and the values to
  expect (unweighted φ 32.932°, S_zz 0.43075, Δ 0.18524; weighted, and flagged inadequate, φ
  32.975°, S_zz 0.43097, Δ 0.18395); how to report; **the severities S1–S3**; the beta's limits.
  The release does not include the 8CB couplings; the guide says that the repository keeps a
  validation copy and asks testers to work from the publication.
- **Issue forms** (`.github/ISSUE_TEMPLATE/`): a bug report (severity S1–S3 and the version
  required) and a reproduction report for the exercise (outcome, route, the unweighted result,
  the version, time taken, what was unclear; it asks testers not to paste the transcribed data).
- **Release notes** (`docs/release-notes/0.1.0b1.md`): what the beta does, how to install, its
  known limits, how it was validated, credits. Its links are absolute, since it is also the
  release's text.
- **A release workflow** (`.github/workflows/release.yml`): pushing a tag `v<version>` checks
  that the tag is both packages' version and has release notes, builds the wheels, runs the
  user's-path smoke test on them, and creates a **draft** GitHub release with the wheels and the
  notes (marked pre-release for a/b/rc versions). Nothing is published until the owner publishes
  the draft. Not yet exercised on GitHub (it runs only on a tag push); its version check was run
  locally (the right tag passes, a wrong one fails).
- **Tests**: `tests/test_beta_docs.py` (the issue forms are valid, the bug form requires the
  severity and the version, every relative link of the README and the user, beta, notebook and
  release documents resolves, the release notes name this version and its wheel, the guide's 8CB
  values equal the frozen fits to their printed digits); `web/e2e/eightcb.spec.ts` follows the
  guide's in-app route click for click on the three browsers and gets the guide's values
  (skipped if the third-party dataset is absent).
- PyYAML joins the development dependencies.

## Before review

**Mutation checks** (each makes a test fail): a broken link in the testers' guide; a guide value
off by 1e-4 in S_zz.

**Baseline (before review):** 882 Python (`-m "not slow"`), Ruff, mypy, the contract; the new browser test on the three browsers (the suite is now 114 = 38 × 3; web code unchanged).

## Round 61: NOT READY (two A, three B), on commit 2d914f3

The reviewer confirmed the 12 mappings, the values and their rounding, the weighting, adequacy
and 1–2 % wording, the forms and heading anchors, the severities, and the workflow's draft and
pre-release flags, wheel selection and toolchain. Its run: 882 Python, Ruff, mypy, the contract,
the notebooks, the build, the three browser tests, a scratch wheel build and smoke test.

1. **(A) The release's source archives would have included the 8CB couplings.** GitHub attaches
   the tag's source archives to every release; `git archive` contained the dataset's
   `couplings.csv` and its expected files (which hold the observations), contradicting the
   owner's choice and the guide. **Fix:** the dataset is `export-ignore`d in `.gitattributes`
   (the directory and every file); the release workflow refuses to draft if the source archive
   contains it; a test checks the attribute on every file of the dataset. `git archive` now holds
   none of it, and the synthetic dataset is kept.
2. **(A) The release's version check accepted unequal versions:** as a regex, `0.1.0b1` matched
   `0.1+0b1` and `0!1.0b1`. **Fix:** literal comparisons (`grep -Fqx`); the reviewer's mutant is
   now rejected and the right version accepted.
3. **(B) The documentation tests proved less than claimed.** **Fix:** the link test also reads
   titled, angle-bracket and reference-style links (with a test of the parser); the form test
   requires labels, unique options, boolean `multiple` and `required`; a new test requires the
   guide's thesis-label → pair table to equal the dataset's mapping (a changed pair now fails).
4. **(B) Displayed precision:** the guide says the app shows values rounded to their uncertainty,
   and that a value rounding the same way agrees.
5. **(B) Retrying a release:** the workflow refuses to touch an existing release, and its header
   says how to retry (corrected in round 62).

## Round 62: READY WITH MINOR CHANGES (one B), on commit 1b5117b (final under the cap)

The reviewer confirmed both class-(A) fixes: the local and the GitHub-generated tar and zip
archives leave out the 8CB dataset, keep the synthetic data and contain no copied coupling
values, and the archive guard rejects the earlier leaking commit; the version mutants, and the
broken-link, form-schema and pair-mapping mutants, are rejected. With mocked GitHub commands it
confirmed the existing-release refusal and the draft and pre-release arguments. Its run: 883
Python (the two build-dependent skips then passed), the 15 documentation tests, Ruff, mypy, the
contract, the three notebooks, the web typecheck and the 8CB exercise on the three browsers, a
wheel build and the clean-install smoke test. The live, tag-triggered release workflow remains
unexercised until the owner pushes a tag.

1. **(B) The retry advice was wrong:** pushing an unchanged tag again starts no run. **Fix:** the
   workflow's header and its error message say to delete any partial draft and re-run the failed
   workflow (Actions, or `gh run rerun RUN_ID --failed`).

Under the cap, this fix was not reviewed again.

**CI after round 62.** The browser job failed once on Firefox in `eightcb.spec.ts`: the model's
"Apply" stayed disabled, because the couplings import's new project description arrived after
the model's selects were changed, and the model draft was reset on every science change, wiping
the edit (the same pattern as the torsion fields in M3 step 4b). A user editing the model while
another client changes the project would have lost the edit too. **Fix:** the model draft follows
the model itself, not every science change. Test: `tutorial.spec.ts` "a science change while the
model is edited keeps the edit" (another client changes a coupling while the kind is edited); it
fails with the old reset. The browser suite then passed: 117 tests (39 × 3).
