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
