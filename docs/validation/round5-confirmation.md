# Round 5: confirmatory architecture review

Reviewed 2026-11-07: redesign plan v0.5, AI-ready architecture v0.2, round-4 requirements, and the listed dataset/citation changes.

**Verdict: READY WITH MINOR CHANGES** to approve v0.5 + 04 v0.2 as the Phase-1 execution baseline. The scientific correction and application boundaries are now adequate to begin M0. Resolve items 1–3 below in its binding ADRs before implementing those contracts; freeze item 4 before M1 evaluation. This approves the design, not an implemented engine or a redistribution licence.

## Disposition of the ten required changes

1. **ADDRESSED — Equivalence/jumps:** plan §4 and D19 require ring-B relabelling; the experimental design permutes both endpoints; M1 covers all pairs, reversal, explicit averaging and the endpoint, without claiming a unique mechanism.
2. **PARTIALLY — Scientific gates:** noiseless recovery, fixed noisy regression, separate coverage and weighted/unweighted configurations replace the failed interval gate; full prediction targets and numerical acceptance policies still need freezing (item 4).
3. **ADDRESSED — Revisions/jobs:** §8.1 separates domains, requires atomic revision checks, deduplicates retries, snapshots job inputs and retains stale results with one terminal cancellation/completion outcome.
4. **PARTIALLY — Replay/undo:** §8.2 supplies forward payloads, content references, IDs, lineage and chronological audited undo; recovery of incomplete multi-event transactions needs an explicit rule (item 3).
5. **PARTIALLY — Policy/proposals:** credential-derived identity, human approval, atomic dependency-closed proposals and bounded dry runs are specified; the capability matrix conflicts with query and assistant wording (item 1).
6. **ADDRESSED — Perception:** §8.4 specifies one shared scene/view, matching perspective parameters, projected/depth comparisons and revision-aware descriptions; transient gestures stay local.
7. **PARTIALLY — Registry/compatibility:** one dispatcher, transport exceptions, boundary/parity checks and semantic breaking changes are covered; unknown input enums need a safe, unambiguous rule (item 2).
8. **PARTIALLY — Roadmap/checks:** M0 is a vertical slice, operations grow with UI need, §8.6 adds the missing failure checks, and A3 precedes the assistant; obsolete cross-references remain (item 5).
9. **ADDRESSED — MCP:** §8.7 attaches the bridge to the existing authenticated session, defines tools/resources/errors/jobs and fallback clients, and commits A1 to pinning the protocol and SDK.
10. **ADDRESSED — Provenance:** the README records source/table/pages/columns, checksum and the owner's stated public-publication basis; experimental data are excluded from BSD, distinguished from the 2010 geometry, and cited in CFF. This documents the basis without establishing external permission.

## New errors and remaining items

1. **Resolve policy contradictions.** In 04 §8.3, “Queries” grants `read` access to `fit.preview`, which D13 calls a query, while the compute row denies it. Exclude bounded preview from the general query grant or explicitly grant it under a preview budget. Also qualify plan A4's “no agent action” approval rule: the matrix deliberately permits direct logged view writes and own-job cancellation. State exactly which effects require approval.
2. **Reject unknown input enum values.** §8.5 distinguishes input/output handling for fields but then maps unknown enums to `unknown` without direction. Restrict that fallback to output decoding; reject unsupported command enum values before dispatch. Otherwise an unknown effect/model can pass validation without defined semantics.
3. **Complete transaction recovery.** “Fsync the event, then acknowledge; truncate a torn final record” does not cover a crash after a complete prefix of a multi-event transaction. Define a durable transaction commit marker (or one atomic transaction record), discard uncommitted prefixes on replay, and make referenced blobs durable before commitment. Persist the request ID/outcome with that commitment so crash/retry cannot apply twice.
4. **Make M1's numerical gates executable before evaluation.** Pin full-precision prediction vectors, per-quantity tolerances, the grid-versus-refined optimum convention, and the coverage ensemble size/acceptance band. The checked-in experimental report contains rounded parameters/RMS, not prediction vectors. Use unrounded forward calculations for the 1e-8 noiseless test; the CSV truth values are rounded. These are fixture specifications, not reasons to redesign the architecture.
5. **Clean up stale guidance.** Replace plan §9's freezer/WebKitGTK/signing risk and “A4 red-team” reference with browser delivery and A3. Update D9's “before a licence is chosen” wording to the already chosen BSD decision. Explicitly subordinate 04 §7's “accepts half” test to dependency-closed acceptance and its transport scan to §8.5's exceptions.

**Verification:** both fit scripts reproduced their stored reports in temporary copies. The corrected experimental design was finite and reversal-invariant for all 45 pairs at 37° and 90°. The rigid 37°/143° equivalence with simultaneous relabelling agreed within 3.2e-12 Hz. No runtime application, crash-recovery implementation or rendering parity exists here to certify. Only this report was written in the project.
