# Validation rounds 41–42: M3 step 2 (Structure view, couplings reconciliation, staleness by content)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

## What the step delivers

- **The owner's decision on staleness:** a run or job is stale when the science differs from its
  input *by content* (ADR-0011 amendment). An undo that restores the exact input makes it current
  again, including across a couplings import (the coupling-ID allocator is excluded) and after a
  restart (the content hash is derived on replay, never journaled).
- **A minimal Structure view** (03 §5): the shared scene drawn in the browser with projection.ts
  (pixel-identical to the server's renderer), couplings as misfit arcs whose colour *and* width
  encode |residual|/σ, atoms and arcs that select in the shared view (shift-click adds), layers,
  "fit to view", a legend and a couplings table as the alternative to every 3D action. Drag, the
  arrow keys, + and − move a local camera at once; it is committed with `view.set_camera` once per
  gesture (keys and the wheel after 400 ms of quiet).
- **Couplings CSV reconciliation in the browser** (D5): `couplings.reconcile` proposes exact label
  matches; every label has a native select, so the mapping can be done from the keyboard; a spin
  chosen twice is flagged before the server is asked; the diff lists each pair's values now and
  after the import (new in the contract: `PairOut.before` and `after`); the import sends exactly
  the mapping the shown diff was computed for, at that diff's science revision.
- **Stricter numbers:** CSV values and XYZ coordinates must be plain ASCII decimals. `float()`
  alone accepted `1_000`, Unicode digits and `nan`; a decimal comma is never guessed.
- Contract 0.7.0. `render.scene` is a page resource, re-read on science, workspace and job lines.

## Before review: found by driving the page

The page was run against `dipolar serve` in Chromium (1440 × 900): open the example, fit, orbit by
keys and drag (one commit per gesture), select by click and shift-click, import a CSV with an
unmatched label (blocked, then a collision, then a valid choice and the import), undo, and a
camera set by the robot's token appearing in the page.

- **An undo across a couplings import left the run stale.** The import advanced
  `next_coupling_id`; undo keeps the allocator advanced by design, so `science_hash` differed. The
  staleness comparison now uses `content_hash`, which excludes the allocator.
- The Structure view's scene was laid out in the narrow side track; the columns were swapped.
- The import button read "Import 0 couplings" while the mapping was incomplete.
- A pair whose value and σ are unchanged but whose provenance changed is now labelled as such.

Mutation checks (each break makes a test fail): staleness by science hash instead of content;
no content hash derived on apply; no decimal check in the CSV parser; none in the XYZ parser;
before and after swapped; the outdated-mapping guard removed (web); the dolly's far plane not moved
(web).

## Round 41: NOT READY (three A, three B), on commit a43ceb7

The reviewer found no defect in content-based staleness, replay, number parsing or contract
generation; 196 focused Python tests, the 28 web tests, mypy, Ruff, the type check, the build,
projection parity, the snapshot and codegen checks passed.

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **A delayed camera commit overwrote a newer camera.** A key's commit, due 400 ms later, still went out after another client's camera arrived, or after "Fit to view". | `CameraCommits` (scene/view.ts) owns every commit: a pending camera belongs to the workspace revision it started from and is cancelled at once when a newer revision arrives; "Fit to view", the 0 key and a drag supersede it. "Fit to view" moved into the Structure pane so it goes through the same path; a refused commit drops the local camera. Tests: `a delayed camera commit is dropped when a newer revision arrives first`, `fit to view supersedes a pending key commit`. Both sequences were also replayed in the browser. |
| 2 | A | **Zooming in and back out shifted the near plane** (4.6 → 12.3 Å; 7 of 10 atoms visible), because a clamped near plane was carried forward. | `dolly` sets the planes from the distance and the molecule's extent about the target alone (distance ∓ 2·radius, as autoCamera), never from the previous planes. Test: a 12-step zoom in and out across the clamp restores both planes and every atom's visibility. |
| 3 | A | **The valid label `__proto__` could not be reconciled:** assigning it to a plain object changed the prototype, and an inherited-property `in` check counted it as mapped. | `effectiveMapping` builds the mapping with `Object.fromEntries`; membership uses `Object.hasOwn` (`spinOf`). Test: labels `__proto__`, `constructor`, `toString`, `hasOwnProperty`. |
| 4 | B → fixed | Camera moves could exceed the server's limits (far past 1e6 Å). | `withinLimits` mirrors `check_camera`; a move the server would refuse leaves the camera unchanged (`guarded`). Test added. |
| 5 | B → fixed | The diff showed one decimal, hiding 0.123 → 0.124. | `comparable` (format.ts) shows both sides at the finest place their uncertainties need, finer still when two different values would read the same. Test added. |
| 6 | B → fixed | Only the first 200 pairs of each kind could be inspected. | "Download the full diff (CSV)": every pair at full precision; text cells quoted, and formula-like cells prefixed with an apostrophe. Test added. |

Mutation checks: the revision cancellation in `CameraCommits.observe`, the dolly planes, the
server-limit guard, the own-property mapping and the distinguishing loop in `comparable` each
make a test fail when broken. The re-check in `CameraCommits.fire` is a backstop behind
`observe` (only reachable if a revision were never observed); breaking it alone fails no test.

## Round 42: NOT READY (two A, two B), on commit d43f3ec

The reviewer confirmed that "fit to view" supersedes pending commits, that StrictMode does not
duplicate commits, that a drag after a remote camera update rebases and commits once, that
prototype-like labels map correctly, that normal moves respect the bounds and that a 1 001-row
CSV keeps every row at full precision. Content staleness, replay and the fallback showed no
further defect. All checks passed (779 Python tests, 34 web tests, mypy, Ruff, codegen, type
check, build, parity).

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **A delayed camera commit could still overwrite a newer camera:** the pane watched only the scene's workspace revision, and the view and scene reads answer independently; `view.set_camera` had no precondition. | `view.set_camera` takes an optional **`expected_workspace_revision`** and refuses a stale camera with `REVISION_CONFLICT` (atomic, in the commit plan). Every gesture commit names the revision of the camera it was moved from; "fit to view" stays unconditional. `CameraCommits` also observes the newest revision from either read and never schedules or sends a camera moved from an older view; a refused commit is quiet and re-reads the view. Tests: `a camera from an older view is refused when the caller says so` (Python), `a camera moved from a view older than any response has shown is never sent` (web). Replayed in the browser. |
| 2 | A | **The CSV formula guard missed labels starting with LF or a space.** | Every text cell that does not start with a letter or a digit is prefixed with an apostrophe. Test: LF, CR, tab, leading space, quotes and formula characters. |
| 3 | B → partly fixed | `comparable` hid a change in σ alone, a change in a value near 1e-100, and mangled values ≥ 1e21. | It now separates differing uncertainties as well as values, down to a double's range; `fixed` writes values ≥ 1e21 in scientific notation. The full-precision CSV remains the complete record. |
| 4 | B | Zoom resets deliberately set clipping planes to the molecule's extent. | Documented policy: the minimal Structure view frames depth automatically when zooming (it is what made the round-41 near-plane fix exact). A client that needs custom clipping sets the camera through `view.set_camera` and should not zoom in the browser afterwards. |

Mutation checks: the server precondition, the two old-view guards in `CameraCommits`, the CSV
text-cell rule and the σ comparison each make a test fail when broken. Under the cap, the round-42
fixes were not reviewed again.

## Known limits (B, documented)

- **The default view of the template looks down the inter-ring axis**, so the biphenyl example
  first appears small; one rotation gives the side view. A better automatic view direction
  changes the server's camera and the parity fixtures; it is left for the Structure view's
  later work.
- **Zoom reframes the depth planes** (round 42, item 4).
- **The diff table shows 200 rows per kind**; the CSV download has every pair.
- **Content staleness falls back to the science hash** for a job whose content hash cannot be
  derived (the recorded hash does not match the state it was applied to); then an undo across an
  ID-allocating import leaves the run stale, as before this step.
- The `CameraCommits.fire` re-check is a backstop behind `observe` and has no test of its own.
