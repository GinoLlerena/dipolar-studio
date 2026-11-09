# Validation round 10: the M0 spikes

- **Reviewer:** GPT-6.1-Sol (Codex, reasoning effort high), read-only.
- **Date:** 2026-11-08.
- **Scope:** `git diff m0-step3..0797d50`, which covers the four M0 spikes (step 4) and the
  re-baseline proposal (step 5).
- **Evidence report:** [docs/spikes/m0-spikes.md](../spikes/m0-spikes.md).

## Verdict

**NOT READY** as the M0 completion baseline. One major finding: an attacker who saw a live launch
code could get a lasting human credential. The other six findings are minor.

## Findings and fixes

All seven findings are fixed. Each fix has an automated test, except where noted. The tests for
findings 1, 2 and 3 were mutation-checked: each fails when the old behaviour is restored.

1. **Major. Winning the launch race granted lasting access.**
   - **The problem.** Browser launchers take the URL as an argument, and other local users can
     read process arguments.
   - **The reviewer's reproduction:**
     - a `BROWSER` launcher exposed the code to `ps`;
     - another user redeemed the code first, forging an allowed `Origin`;
     - the real page got 401, and the attacker kept a working token.
   - **The fix.** `dipolar open` and `serve --open` write the URL into a private redirect page:
     mode 0600, in a mode-0700 `browser-launch/` directory. The launcher receives only that file's
     path. This is Jupyter's approach. Round 11 hardened the directory handling (see below).
   - **The threat model is now explicit in ADR-0010:**
     - processes of the same OS user are trusted;
     - other local users and other origins are not;
     - a stolen code yields a token that only a restart revokes.
   - **Test.** `test_the_browser_launcher_never_sees_the_code` uses a recorder script as the
     browser. It checks that the launcher receives only a `file://` path, checks the file and
     directory modes, and confirms the code inside still opens a session.
   - **By hand.** Headless Chromium followed the `file://` redirect page to the app and connected.
2. **Minor. Unpaired surrogates and deep nesting produced plain 500s.**
   - **The fix.** One shared iterative check, `schemas.wire_problem`, refuses invalid Unicode and
     nesting deeper than 64 levels. The HTTP parser and the dispatcher both use it, so both
     adapters return `INVALID_ARGUMENT`. The parser also catches `RecursionError`, and launch codes
     must match `[A-Za-z0-9_-]{1,64}` before hashing.
   - **Tests.** HTTP bodies, the code exchange, the Python adapter and cyclic Python arguments.
3. **Minor. Tab tokens could mint launch codes.**
   - **The fix.** Every token carries its provenance, launch or tab. Only the human *launch* token
     mints.
   - **Tests.** A unit test, and a test over HTTP against the packaged build.
4. **Minor. The crash harness could undercount acknowledgements.**
   - **The fix:**
     - one unbuffered reader with an explicit line buffer, which drains to end of file after the
       kill;
     - on a timeout, the child is killed before its diagnostics are read;
     - a harness self-check: each run's acknowledgements must be contiguous and start right after
       the recovered sequence, so a dropped line shows up as a gap.
5. **Minor. The numerical finding overstated its explanation and precision.**
   - **Confirmed by measurement:**
     - χ²(φ) still distinguishes offsets of 10⁻¹² °;
     - the scalar refiner's 1.5·10⁻⁹ ° is where its own tolerance stops it;
     - on the noisy fixture, the residual-vector refiner differs from the frozen optimum by
       2.3·10⁻⁹ °, not 4·10⁻¹³ °. The 4·10⁻¹³ ° figure was scalar against scalar.
   - **The fix.** The report and ADR-0003 now call these observations specific to each algorithm.
     The test holds the residual-vector refiner to absolute requirements: within 10⁻¹² ° of the
     noiseless truth and within 10⁻⁸ ° of the frozen noisy optimum.
6. **Minor. Schema acceptance and runtime acceptance differed.**
   - **The problem.** The published schema accepts `expected_science_revision: 0.0`, but strict
     validation refused it.
   - **The fix.** JSON has one number type, so an integral number within ±(2⁵³ − 1) is read as an
     integer before strict validation. `0.5`, `true` and `"0"` stay refused. The docstring now
     says plainly that Python tuples become arrays.
7. **Minor. A failed exchange could leave the page stuck at start-up.**
   - **The fix.** `startTabSession` never rejects. A malformed fragment such as `#launch=%` leads
     to a refused exchange and the launch guidance.
   - **Verified by hand** in Chromium. There are no automated browser tests until M3.

## Checked and found correct by the reviewer

- **Tests and tooling.**
  - 162 tests, lint, formatting, mypy and the frontend build pass.
  - The installed-wheel D10 suite passes, and the build left the source tree clean.
- **Science.**
  - The weighted projection is correct.
  - The planar and collinear identification claims are correct.
  - The rank-changing null space is correct.
  - The prototype follows the frozen grid-and-refine convention.
  - The full-Jacobian covariance holds the order parameters fixed and whitens once.
- **JSON.**
  - The adapters behave alike.
  - Coercion is rejected, and only finite numbers pass.
  - Revisions are bounded, and duplicate keys are refused in nested objects too.
  - The examples, results and error envelopes all validate.
- **Security.**
  - The Host and Origin allow-lists match exactly, and a missing Host is refused.
  - CSRF is blocked and no CORS headers are sent.
  - Static-file traversal is refused.
  - Token comparisons are constant-time, the credential table is locked, and the caps hold.
- **Lifecycle.**
  - The POSIX lock is taken before the journal and the ready file are touched. Keeping the lock
    file avoids an inode-replacement race.
  - A stale ready file is replaced, and both client handshakes work.
  - The impostor test does not depend on reusing a connection in TIME_WAIT.
- **Durability.**
  - Under the model of a single writer killed mid-process, the record is fully written and fsynced
    before it is acknowledged.
  - Fail-stop prevents an append after a torn write.
  - The order quarantine, directory fsync, then truncation is sound.
  - A complete record that was never acknowledged may legitimately survive a restart.
- **Frontend and docs.**
  - Exchanging the code once at module level avoids a double redemption under StrictMode.
  - The fragment is stripped before the fetch.
  - `UNAUTHENTICATED` clears the stored token.
  - The re-baseline is a reasonable proposal and sets no dates.
- **HTTP is a reasonable transport for the beta.**

## Round 11: confirmation

- **Reviewer and date:** the same reviewer, read-only, 2026-11-09.
- **Scope:** commit fdb1a1d.
- **Verdict: NOT READY.** All seven round-10 findings are resolved. The fix for finding 1
  introduced a new major problem.

**The tooling passed:** 181 tests, lint, formatting, mypy, the web build, and 29 D10 tests on the
installed wheel. **Other checks** found no blocker:
- HTML escaping of the redirect URL works;
- an existing 0777 directory becomes 0700;
- strict parsing of a 1 MiB body holding 349,518 strings takes about 0.13 s.

**New findings, all fixed:**

1. **Major. A symlinked `browser-launch` directory led to changes outside the project.**
   - **The problem.** Shutdown deleted matching files in the symlink's target, even without
     `--open`, and `open` chmodded the target.
   - **The fix.** The redirect directory sits beside the ready file and is checked with `lstat`. It
     must be a real directory owned by the user; a symlink, a non-directory or another user's
     directory is refused. Its mode is forced to 0700. Page names carry the instance ID, and cleanup
     deletes only regular files: at shutdown, only this instance's pages.
   - **Test.** `test_a_symlinked_launch_directory_is_refused_and_never_touched`, which was
     mutation-checked.
2. **Minor. Relative project paths broke the browser launch.** `as_uri()` needs an absolute path,
   and `serve --open` failed before its cleanup block. The fix: absolute paths, and the launch now
   happens inside the cleanup scope. Tests cover `open` and `serve --open` with relative paths.
3. **Minor. A ready file in a custom location escaped cleanup.** The fix: `open`, `serve --open`
   and shutdown all use the directory beside the ready file. There is a test.
4. **Minor. The documents overclaimed.** The fix:
   - ADR-0010 now says the ready file is the one file holding launch secrets;
   - the report names the code exchange as the one response that carries a token;
   - the shutdown cleanup is described as graceful shutdown only, with leftovers after a SIGKILL;
   - STATUS gives the actual verdicts.
