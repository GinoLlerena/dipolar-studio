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
