# M0 step 4: the four spikes

Each spike was asked to pass or fail with evidence (plan §8, M0). All four passed. Each one also
found something that was then fixed.

- **Where the evidence lives:** every spike is an executable test module in `spikes/`, run by CI on
  every push.
- **Reproducing the numbers below:** run `uv run pytest -s spikes/`.

| Spike | Verdict | Findings fixed | Decision taken |
|---|---|---|---|
| 1. D3 numerical controls | **Pass** | none needed in the code (one M1 method observation) | M1 refines on the residual vector |
| 2. JSON serialization | **Pass after fixes** | type coercion, NaN handling, lax JSON parser, unsafe integers; in round 10, surrogates and deep nesting | strict JSON validation; envelopes published |
| 3. D10 localhost security | **Pass after fixes** | stale ready file; no instance handshake; no single-instance guard; in round 10, the code on the launcher's argv and minting by tab tokens | launch-code hand-off through a private redirect page; HTTP transport for the beta |
| 4. Journal crash recovery | **Pass** | the planned recovery, now implemented | discard a torn tail; fail-stop still needs a restart |

## 1. D3 numerical controls

`spikes/test_spike_d3_numerics.py` has 12 tests.

**Question.** Does dipolar-core's inner solve pass the D3 controls? It is wrapped in a small
prototype fit (a grid, then refinement). Does that fit reproduce the frozen fixtures, which
`tools/reference/` produced independently?

The prototype uses only dipolar-core's public functions and SciPy. It is spike code, and M1
replaces it with the real D3 stack.

### Evidence

**Weighted-projection control (D3.7).** With A = (1, 1)ᵀ, y = (0, 1)ᵀ and L = diag(1, 2), the
solve gives t\* = 0.8 and χ² = 0.8, exact to 10⁻¹⁵.

**Planar and collinear data (D12).**
- Twelve coplanar vectors in a random orientation give rank 3. The in-plane block of S and the
  normal component are recovered to 10⁻¹². The null space is exactly the two couplings between
  the normal and the plane.
- Collinear vectors give rank 1, and they recover only cᵀSc.

**Rank-changing path.** All five S components are free, and the molecule flattens as φ → 0.

| φ (°) | 1 | 10⁻² | 10⁻⁴ | 10⁻⁶ | 10⁻⁷ | 10⁻⁸ | 10⁻⁹ … 0 |
|---|---|---|---|---|---|---|---|
| inner rank | 5 | 5 | 5 | 5 | 4 | 4 | 3 |
| condition number | 1.77·10³ | 1.77·10⁵ | 1.77·10⁷ | 1.77·10⁹ | n/a | n/a | n/a |

- While the rank is full, condition × φ is constant to 1%.
- The rank then drops monotonically under the written policy (RANK_RTOL = 10⁻¹⁰).
- At φ = 0 the null space is exactly span{Sxy, Syz}, because the molecular plane is xz.
- The flags are honest throughout:
  - either the rank is full and a finite condition number shows how close the problem is to
    singular;
  - or the rank is reduced and no condition number is given.

**The two-parameter rigid model (Szz, Δ).** Its rank is 2 everywhere on [0°, 90°] and its
condition number stays below 10. In this model the "rank change" exists only in the five-component
tensor.

**Grid, then refine, against `noisy_fixture.json`.** All differences are far inside the frozen
tolerances.

| Quantity | Difference | Tolerance |
|---|---|---|
| φ | 4.5·10⁻¹³ ° | 10⁻⁴ ° |
| Szz, Δ | 1.1·10⁻¹⁵, 5.3·10⁻¹⁵ | 10⁻⁶ |
| predictions (max) | 2.1·10⁻¹¹ Hz | 10⁻⁶ Hz |
| χ² (relative) | 1.5·10⁻¹³ | 10⁻⁶ |
| full-Jacobian standard errors (relative) | ≤ 6.3·10⁻¹⁰ | 10⁻³ |
| φ, Szz, Δ profile-interval endpoints | pass | 10⁻⁴ °, 10⁻⁶ |

The grid-best point and both competing basins are reproduced: 37.0° (χ² 15.76) and 79.5°
(χ² 2.6·10⁶). The inner condition number (3.3153) and the joint rank (3) match.

**Full fit versus reduced fit (D3.7).** A bounded joint TRF fit over (φ, Szz, Δ) lands on the
VarPro (profile) optimum:
- φ agrees to 10⁻⁶ ° and S to 10⁻⁸;
- 2·cost equals χ² to 10⁻¹⁰.

**Noiseless recovery.** φ, Szz and Δ are recovered within the 10⁻⁸ gate.

### Observation: an M1 method choice

*Corrected after validation round 10, finding 5.* Two refiners of the same profile were
compared. Both results are specific to the algorithm used, and neither shows a fundamental
precision limit.

- **Scalar refinement** (SciPy's bounded scalar minimizer). This is the frozen optimum convention,
  and `tools/reference/` uses it too. It stops at its own tolerance: 1.5·10⁻⁹ ° from the noiseless
  truth, although χ²(φ) still distinguishes offsets of 10⁻¹² °. On the noisy fixture it matches the
  frozen value to 4·10⁻¹³ °, because the reference used the same algorithm.
- **Residual-vector refinement** (bounded TRF, as D3.1 prescribes). It recovers the noiseless
  truth to rounding, and differs from the frozen noisy optimum by 2.3·10⁻⁹ °. That is far inside
  the 10⁻⁴ ° regression tolerance.

**M1 refines with `least_squares` on the residuals.** It is held to absolute requirements:
- within 10⁻¹² ° of the noiseless truth;
- within 10⁻⁸ ° of the frozen noisy optimum.

The frozen expected values stand.

## 2. JSON serialization

`spikes/test_spike_json_serialization.py` has 13 tests, and there are regression tests in
`packages/dipolar-app/tests/`.

**Question.** Is the published contract honest? Could a client that knows only the registry
snapshot build valid requests and read every response? The check uses `jsonschema`, an
independent validator, rather than Pydantic, which produced the schemas.

### Evidence

- Every published schema is valid JSON Schema (draft 2020-12): both envelopes, plus the input and
  output schemas of each of the five operations.
- Every example validates against its operation's input schema. Every result validates against
  its output schema and the success envelope.
- All 12 error codes were produced, ten through the dispatcher and three by the HTTP adapter. Each
  validates against the error envelope, and the error envelope lists exactly those codes.
- Results round-trip losslessly: JSON → strict model → JSON gives the same text, with every float
  exact.
- Units are visible as constants in the schemas (`"const": "deg"`, `"Hz"`, `"Å"`). ID patterns are
  visible too (`^(spn|cpl)_[0-9]{6}$`).

### Findings, all fixed

1. **Type coercion.** Pydantic's default lax mode accepted:
   - `"37"` and `true` as numbers;
   - `"1"` as an integer;
   - `false` as `expected_science_revision: 0`, so a wrong type could pass a revision check.

   The fix: the dispatcher now validates every adapter's input in **strict JSON mode**. There are
   regression tests, and they fail if strict mode is removed.

   **Changed in round 10 (finding 6).** JSON has a single number type, and the published schema's
   "integer" accepts `0.0`. An integral number within ±(2⁵³ − 1) is therefore read as an integer
   before validation, so runtime acceptance matches the published schema. A test checks this.
   `0.5`, `true` and `"0"` are still refused.
2. **NaN through the Python adapter.** `LocalClient` raised `ValueError` on NaN or ±inf instead
   of returning an error. The fix: the dispatcher serializes the arguments itself and returns a
   structured `INVALID_ARGUMENT`.
3. **A lax HTTP JSON parser.** Python's `json.loads` accepted:
   - the tokens `NaN`, `Infinity` and `-Infinity`;
   - duplicate keys, where the last one silently wins (a request-smuggling vector, because parsers
     disagree);
   - UTF-16 and UTF-32 bodies.

   The fix: strict RFC 8259 parsing. `1e400`, which overflows to infinity, is refused by the
   dispatcher's finite-number check.

   **Round 10 (finding 2)** found two inputs that still produced a plain 500:
   - unpaired surrogates, for example a `"\ud800"` key or value;
   - deep nesting, such as 10,000 nested arrays.

   Both adapters now refuse them with `INVALID_ARGUMENT`, using one shared iterative check that
   allows at most 64 levels of nesting. That check also stops cyclic Python arguments.
4. **Integers unsafe for JavaScript.** Revision inputs are now bounded to 2⁵³ − 1, and the schema
   says so.
5. **Unpublished envelopes.** The snapshot now publishes the success and error envelopes,
   including the error codes. That lets the M2 TypeScript generator type errors as well as
   results.

## 3. D10 localhost security on a packaged build

`spikes/test_spike_d10_localhost.py` has 29 tests. `packages/dipolar-app/tests/test_app_auth.py`
covers the credential logic with a fake clock.

**Question.** Can a browser page and scripts use a local `dipolar serve` safely, and does the
*installed package* hold the controls, not only the source tree?

`tools/package/build.sh` bundles the built page into the `dipolar-app` wheel. The suite then runs
against the `dipolar` executable of a clean virtualenv: `DIPOLAR_BIN=…/bin/dipolar`. A new CI job
does exactly this on every push.

### Decision: the browser hand-off

This was the open D10 question.

| Option | Verdict |
|---|---|
| Paste the token from the ready file (M0 slice) | rejected: poor UX, and it teaches people to copy secrets |
| Long-lived token in the URL fragment | rejected: it ends up in browser history and sync, and in the arguments of the process that opens the browser |
| HttpOnly cookie | rejected: cookies are not isolated by port, so other localhost apps and other instances collide (cookie tossing). SameSite does not separate ports either. |
| **Single-use launch code → tab token** | **chosen** |

How the chosen hand-off works:

1. **Mint.** `dipolar open --project-dir DIR` (or `dipolar serve --open`) reads the private ready
   file and checks the instance handshake. It then asks the server for a **launch code**:
   - single use;
   - valid for 60 s;
   - minted only with the human *launch* credential from the ready file. A tab token acts as the
     user but cannot mint (round 10, finding 3);
   - at most 8 pending at a time.

   **The code never appears on a command line** (round 10, finding 1). Browser launchers take
   their URL as an argument, which other local users can read with `ps`. So `dipolar open` writes
   the URL into a private redirect page: mode 0600, in the mode-0700 directory
   `<project>/browser-launch/`, removed at shutdown. It gives the launcher only that file's path.
   This is the approach Jupyter uses for the same problem.
2. **Open and exchange.** The redirect page sends the browser to `/#launch=<code>`. The fragment
   never reaches the server. The page removes it from the address bar first, then exchanges the code once, from an
   allowed `Origin`, for a **tab token**. At most 32 tab tokens are issued per instance.
3. **Keep.** The tab token lives in `sessionStorage`. That storage is scoped to this origin
   (including the port) and to this tab; it survives a reload and is gone when the tab closes.
4. **Restart.** After a server restart the page shows the `dipolar open` command again.

**Threat model.**
- **Processes of the same OS user are trusted.** They can read the ready file and the user's
  browser profile anyway.
- **Other local users and other origins are not.** They never see a launch token, and they never
  see a code: the code is not in any process's arguments, and it lives only in files readable by
  the user.
- **If a code is stolen anyway,** whoever uses it first gets a tab token. Single use, the
  one-minute lifetime and a visible failure on the real page ("already used; if this page never
  used it, someone else may have") limit the damage. They do not revoke a token that was already
  issued. Revoking it means restarting `serve`.
- **`dipolar open --print-url`** prints the URL to the user's own terminal, for headless use only.

Checked by hand:
- **headless Chromium** followed the private `file://` redirect page to the app, exchanged the
  code and connected;
- **in Chromium (Playwright):**
  - a malformed `#launch=%` link shows the launch guidance instead of breaking the page;
  - the fragment was gone on arrival, and the page connected;
- the token was in `sessionStorage` only (no `localStorage`, no cookie);
  - a reload stayed connected;
  - replaying the used link in an isolated context was refused, with that message.

### Evidence (passes on the source tree and on the installed wheel)

**DNS rebinding.** 13 Host variants are refused (400 or 421) on every route type: the page, the
registry, the instance check, operations and the launch-code route.
- The variants: a foreign name with and without the port, the right host with no port or the wrong
  port, `LOCALHOST`, `localhost.`, `0.0.0.0`, `127.1`, `2130706433`, `[::1]`, a suffix attack and an
  empty Host.
- A missing Host is refused over both HTTP/1.0 and HTTP/1.1.

**CSRF.**
- A cross-site `text/plain` "form" POST gets 403.
- The same request without an Origin gets 401.
- `Origin: null` (sandboxed frames, `file://`) gets 403.
- Another localhost port is a different origin and gets 403.
- A valid token with `text/plain` gets 400.
- **No `Access-Control-*` header is ever sent**, so a preflight from a foreign origin gets 403.

**The code exchange.**
- Without an `Origin` it gets 403, and from a foreign Origin 403; neither refusal consumes the code.
- The first exchange returns a new token. The second gets 401.
- Neither a robot token nor a tab token can mint codes (403), and GET mints nothing.
- Odd Unicode, deep nesting and wrong types in the exchange body get a structured 400.
- **The launcher never sees the code.** In a test, the browser is a recorder script standing in
  for any launcher, and it receives only a `file://` path. The page is mode 0600 in a 0700
  directory and holds the code, and that code still opens a session.

**Token leakage.** No credential appears in:
- the server's output, during the run or after shutdown;
- its process arguments (`ps`), or those of the browser launcher;
- the journal;
- the page and its assets;
- any response body or header.

The launch code appears only in the private redirect page and, when asked for, in
`dipolar open --print-url` output. Both are single-use by design.

**Instances.**
- `serve` takes an exclusive lock on the project directory, and the kernel releases it even on
  SIGKILL. A second instance on the same project exits with code 3 and does not touch the first
  one's ready file.
- Two instances on different projects are isolated: A's token gets 401 on B, and A's Host gets
  421 on B.

**Port reuse.** Instance A is killed with SIGKILL, and an impostor HTTP server takes its port. The
impostor answers 200 to anything. Both clients refuse the stale ready file:
- the robot exits 1;
- `dipolar open` exits 4.

They check `GET /api/v1/instance`, which needs a credential, against the ready file's
`instance_id`. A new instance on the same project then starts at once, replaces the stale file,
and the robot completes.

### Findings, all fixed

1. **A stale ready file stayed in place.** After a crash, a new instance left the old file until
   it published its own, so a client could read a dead file. The fix: `serve` deletes it right
   after taking the lock. Holding the lock proves the file is stale.
2. **No instance handshake.** The robot trusted whatever answered on the port. The fix: the
   authenticated instance check, used by the robot and by `dipolar open`.
3. **No single-instance guard.** Two servers could write one journal. The fix: the project lock.
4. **Round 10, finding 1 (major): the code was on the launcher's command line.** The reviewer
   reproduced the attack:
   - a `BROWSER` launcher exposed the code to `ps`;
   - another user redeemed it first, forging an allowed `Origin`;
   - the real page got 401, and the attacker kept a working token.

   The fix: the private redirect page.
5. **Round 10, finding 3: tab tokens could mint codes.** The fix: tokens now carry their
   provenance.
6. **Round 10, finding 7: the page could hang at start.** A failed exchange, or a malformed
   fragment, left it in the "connecting" state. The fix: the exchange never rejects, and a bad
   link shows the guidance.

### Decision: the transport

**HTTP on loopback for the beta.** The browser needs it, and the packaged spike shows the controls
hold. stdio stays the transport for the Phase 3 MCP adapter, which is a separate adapter over the
same dispatcher.

### Remaining for M2/M3 (not blockers)

- The event stream needs authenticated fetch streaming (D10), because `EventSource` cannot send a
  header.
- Windows uses `msvcrt.locking` for the project lock; that path is untested until a Windows CI job
  exists.
- The wheel carries no licence file yet. Add one before any packaged release (D9 checklist).
- Run the negative tests in Firefox and WebKit as well (plan §8 risk table, M3).

## 4. Journal crash recovery

`spikes/test_spike_journal_crash.py` and `spikes/crash_writer.py`, plus unit tests in
`test_app_journal.py`.

**Question.** If the process is killed in the middle of a commit, does the journal come back
consistent, and does every command a client was told about survive?

### Decision: the recovery policy (now in `Journal.recover_torn_tail`)

**A torn tail is discarded.** Bytes after the last newline are a record whose write was cut
short. A record is acknowledged only after its whole line, newline included, is written and
fsynced. So a torn record was never acknowledged, and discarding it loses nothing any client was
told.
- The order of steps: verify every complete line, copy the tail to a private quarantine file
  (`project.events.jsonl.torn-<UTC>-<random>`, mode 0600), fsync the file and its directory, then
  truncate the journal and fsync it.
- A crash between steps only leaves an extra quarantine copy.
- `serve` reports what it discarded.

**Damage anywhere else is refused, and nothing is changed.** A complete line that fails its
checksum may have been acknowledged, so it is never repaired automatically.

**A fail-stopped session still needs a restart.** After an fsync error the kernel may already
have dropped the dirty pages and cleared the error, so a retried fsync can falsely succeed. This
is the 2018 PostgreSQL "fsyncgate" lesson. The process cannot know what reached the disk.
Restarting re-reads the journal as the source of truth and runs recovery. Queries keep working in
the meantime. This decision can be revisited in M2 if the UX needs it.

### Evidence

- **Unit tests.**
  - A tail cut by 1 byte, by 25 bytes or just before the newline is discarded and quarantined byte
    for byte. The earlier records replay, and the next append is clean.
  - A journal holding only a torn record recovers to empty.
  - A damaged complete line, in the middle or at the end, is refused with the file untouched and no
    quarantine.
  - `replay()` on its own still refuses a torn tail; recovery is a separate step.
- **The kill loop.**
  - A child process commits `view.select` in a loop and prints `ack <seq>` after each
    acknowledged command.
  - The parent kills it with SIGKILL at random moments and restarts it on the same journal.
  - In **slow** mode each write stores at most 7 bytes, so kills land mid-record.

  | Run | Kills | Torn tails recovered | Final seq | Acknowledged commands lost |
  |---|---|---|---|---|
  | slow (CI) | 15 | 13 | 47 | 0 |
  | normal (CI) | 10 | 0 | 339 | 0 |
  | slow, long (`-m slow`) | 200 | 195 | 690 | 0 |

  - Every restart opened the journal.
  - Each restart began at or after the last acknowledged sequence.
  - Every discarded byte was in a quarantine file.

  **Mutation check.** A recovery that also drops the last complete record fails the loop at once
  (a lost acknowledged command).
- **The real server.** A `dipolar serve` is killed with SIGKILL and its journal is left with a torn
  record. On restart it reports "Recovered the journal…", keeps every complete record, and the
  robot completes again.

**Out of scope, by design: power loss and storage faults.** A process kill keeps every byte
already in the page cache. Only fsync-acknowledged records are promised to survive power loss, and
no spike simulates it.
