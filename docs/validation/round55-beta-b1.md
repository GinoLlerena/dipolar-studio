# Validation rounds 55–56: beta step B1 (install and run)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

## The beta release, in four steps

The plan's beta release (03 §8): docs with executed notebooks, a summary report, `pip install` +
`dipolar serve`; its exit is two or more external users reproducing the 8CB dataset on their own,
with no open S1 issue. The owner chose on 2026-11-16 that **users bring the 8CB data**: the beta
ships no 8CB couplings; the docs say how to obtain them from the published thesis and reproduce
the fit (the repository keeps its copy for validation only, as before).

1. **B1, install and run** (this step): beta versions, a Python API for users, the user guide, the
   README, and the user's path checked in CI against the installed wheels.
2. **B2, the summary report:** a deterministic HTML/CSV report of a run, as a registry operation
   with a button in the page.
3. **B3, executed notebooks:** the synthetic tutorial, your own XYZ and CSV, and the 8CB
   reproduction from your own transcription; executed in CI (the 8CB notebook against the
   repository's validation copy).
4. **B4, beta readiness:** the 8CB reproduction guide for testers, issue templates with S1–S3
   severities, release notes and the tag. Publishing the wheels (a GitHub release, PyPI) and
   recruiting the testers are the owner's.

## What step B1 delivers

- **Versions 0.1.0b1** for `dipolar-core` and `dipolar-app` (the lock updated), and
  `dipolar --version`: "dipolar 0.1.0b1 (dipolar-core 0.1.0b1, contract 0.9.0)", what a bug report
  needs. A test keeps each `__version__` equal to the installed package's metadata.
- **A Python API for users** (`dipolar_app.api`): `Studio.local(project_dir=None)` (a session in
  the process, as the human user; journaled and locked in `project_dir` if given) and
  `Studio.connect(ready_file, who="user")` (a running `dipolar serve`, over HTTP). `call(name,
  args, **kwargs)` returns the operation's result and raises `OperationFailed` (code, message,
  offending field, hint, details) on a refusal; `envelope(...)` returns the raw envelope;
  `science_revision`, `wait(job_id)` and `fit(intervals=...)` (submit at the current revision, wait,
  `run.get`). Every call is a registry operation, validated as strict JSON as over HTTP. The local
  path imports no web server (a test checks that uvicorn and starlette are not loaded).
- **The instance lock** moved from the CLI to `dipolar_app.instance`, shared by `dipolar serve`
  and `Studio.local`, so a notebook and a server never write one journal at once. Its message now
  says "another Dipolar Studio session is already using …".
- **The user guide** (`docs/user/`): getting started (install, start, a first fit, your own data,
  the models per geometry, Python, the beta's scope, reporting a problem) and file formats (the
  couplings CSV, XYZ, project files), written from the parsers' rules.
- **The README**: the status (M1–M3 complete, the beta in preparation), a "Use it" section, links
  to the guide.
- **The user's path in CI** (`tools/package/smoke.py`, in the "packaged" job): in a clean
  environment with only the two wheels, `dipolar --version`; the guide's Python example, extracted
  from the guide and run as written; `dipolar serve` serving the bundled page; and
  `Studio.connect` fitting through it (φ ≈ 37°).

## Before review

- **Mutation checks:** the guide's example with a misspelt operation fails the smoke test
  (`UNKNOWN_OPERATION`).
- **Tests:** `packages/dipolar-app/tests/test_app_api.py` (6: the principal equals `dipolar
  serve`'s user; a local fit equals the frozen answer; refusals raise with the server's code,
  `envelope` returns them raw, unknown arguments are refused; a journaled session is locked and
  reopens; `connect` drives a running server; no web server is loaded locally);
  `tests/test_boundaries.py::test_the_versions_agree_with_the_package_metadata`.

**Baseline (before review):** 841 Python (`-m "not slow"`), 65 web unit and 108 browser tests (unchanged web code), mypy, Ruff, the generated contract; the smoke test against wheels built from this branch, in a clean virtualenv.

## Round 55: NOT READY (five A), on commit 8bbc852

The reviewer's run: 841 Python and 65 web unit tests, Ruff, mypy, the contract; the wheels built
and the smoke test passed in a clean virtualenv (φ = 36.985°); the smoke test rejected a
misspelt guide operation and a missing page; `wait`'s slicing and timeout and failed or cancelled
fits behaved. All five findings were reproduced.

1. **(A) A closed local session could still write.** Closing A and opening B on one directory,
   then writing through both, left a journal that no longer replayed; and a fit still computing
   in A's worker thread published after `close()` returned (its join gave up after 10 s) and B had
   reopened. **Fix:** `close()` refuses later calls and waits for a call in progress; then
   `Session.stop()` (new) refuses every commit, under the commit lock, so neither a call nor a
   worker writes again (a late result writes no blob either); then the workers stop; only then is
   the project's lock released. Tests: a closed Studio refuses calls and the next one owns the
   journal; a result after `stop()` writes no record and no blob; a fit computing at `close()`,
   and one held after its "closed?" check while publishing, are both recorded as interrupted at
   reopening, with no run (the second fails when `close()` does not stop the session).
2. **(A) A failure after taking the lock kept it.** Opening the journal outside the cleanup (a
   dangling `project.events.jsonl` symlink) left the directory locked for the process. **Fix:**
   everything after the lock (journal, session, runner, client) is inside the cleanup. Test: the
   reviewer's symlink, then a successful open (fails without the cleanup).
3. **(A) A reply that was not an envelope lost its diagnosis** (a plain-text 404 raised
   `JSONDecodeError`). **Fix:** replies are checked as operation envelopes; anything else raises
   `OperationFailed` with code `NOT_AN_ENVELOPE`, the HTTP status (`http_status`) and the start of
   the body, chained to the HTTP error. Tests: the reviewer's `project/describe` (404), and seven
   bodies that are not envelopes.
4. **(A) The guide's rule for equivalent pairs was wrong** (a class that holds on imported
   geometry is accepted). **Fix:** the guide states the actual rules: the class includes the
   coupling's own pair, the multiplicity counts it, no pair is in two couplings, and every pair
   must give the same calculated coupling under the fitted model at several torsions.
5. **(A) The smoke test passed an installation without its scripts and styles.** **Fix:** it reads
   the page's `/assets/` references and requires each to be served, non-empty, with a script or
   stylesheet content type. With the installed assets removed it now fails (404).

**After the fixes:** 854 Python tests; the smoke test against wheels rebuilt from this branch.
