# Validation rounds 29 and 30: M2 step 1b (TypeScript generated from the registry snapshot)

## Round 29

- **Reviewer:** GPT-6.1-Sol (high effort), independent and read-only.
- **Reviewed:** 65fb10a against 2ff8a80 (`m2-step1`).
- **Verdict: NOT READY.** Five class-(A) findings: three major, two minor. Each came with a
  reproducer, several of them built from real Pydantic models.
- **Confirmed without defects:**
  - required, defaulted and nullable fields; explicit `undefined` refused;
  - literals, enums, fixed tuples, dictionaries, nested definitions, and narrowing on `ok` for a
    single operation;
  - discriminated unions (`oneOf`, `discriminator`) and unsupported recursive roots stop
    generation;
  - `ErrorBody` matches the authentication errors;
  - staleness is checked for both generated files, the live-registry chain is complete, the
    output is deterministic, and the digest matches the snapshot bytes;
  - the boundary tests hold, and nothing type-only reaches the bundle.

### Findings and fixes

Each fix has permanent tests: in `tests/test_ts_contract.py`, or in `web/src/contract.typetest.ts`
for TypeScript-level behaviour. Each was mutation-checked: 14 mutations of the generator, all
caught by the tests, and 4 of the TypeScript mechanisms, all caught by `tsc`.

1. **Typed additional properties were widened (major).** Named properties beside a typed
   `additionalProperties` (Pydantic `extra="allow"` with a typed `__pydantic_extra__`) produced
   an index signature of the union of every type. So `{label: "x", other: "not an int"}`
   compiled.
   - **Fix:** refused (`Unsupported`). TypeScript cannot say "these keys have these types, and
     every other key has that type" exactly. The test that had enshrined the widening now checks
     the refusal, with the reviewer's real Pydantic model.
2. **Closed objects were not exact, and closed unions were not exclusive (major).**
   - A variable carrying an extra key compiled as `callOperation` arguments; the server refuses
     it with `extra_forbidden`.
   - Two closed models, `{a: int} | {b: str}`, accepted `{a: 1, b: "x"}`.
   - **Fix, in the generator:** in a union, each closed-object branch forbids the other
     branches' keys (`Left & { b?: never }`), through `$ref`s too. Any other mix of object
     branches (open objects, records) is refused, and so is a union of several array types. A
     branch that accepts any JSON value makes the whole union `JsonValue`.
   - **Fix, at the call boundary:** `callOperation(name, args: A & Exact<OperationInput<N>, A>)`.
     `Exact` maps every key the operation's type does not declare to `never`, at every depth,
     including tuple elements and record values. It distributes over unions, so the arguments
     must fit one branch exactly.
   - **What remains (B, documented):** TypeScript types are structural. A generated type used
     *outside* `callOperation` still accepts a variable with undeclared keys. `Exact` guards the
     one place where the page sends data.
3. **`anyOf`, `const` and `enum` dropped structural siblings (major).** `{"anyOf": [...],
   "required": ["a"]}` rendered as if `required` were absent, an outer `additionalProperties`
   was ignored, and `{"const": "x", "type": "number"}` rendered as `"x"`.
   - **Fix:** beside `$ref`, `anyOf`, `const` and `enum`, only annotations and value-only
     constraints are allowed; any structural keyword is refused. `const`/`enum` may carry `type`
     only if every value has that type. `const` beside `enum` is refused.
4. **The success-envelope guard was partial (minor).** It never checked `result`, and it ignored
   added keywords (`not`, `enum` on `operation`, `unevaluatedProperties`).
   - **Fix:** the envelope, titles removed, must equal one expected schema exactly: every
     keyword, the `required` list, and the set of `$defs`. Seven new mutation cases.
5. **A union of operation names lost the pairing (minor).** `callOperation(flip ? "fit.preview"
   : "view.select", {ids: []})` compiled. `Envelope<"fit.preview" | "view.select">` accepted one
   operation's name with the other's result.
   - **Fix:** `name: N & SingleName<N>`, where `SingleName` is `never` for a union, so a call
     names exactly one operation. `SuccessEnvelope<N>` now distributes over `N`.
   - `App.tsx`'s `run` helper now takes the call itself, `run((t) => callOperation("fit.preview",
     {...}, t))`, so each call site names one literal operation.

**Documented limit (B):** integrality, bounds, patterns and lengths cannot be expressed in
TypeScript. They are doc comments, and the server enforces them; for example,
`expected_science_revision: 0.5` compiles and is refused with `int_type`.

Two of the author's own probes were wrong on the first try:
- `const n: OperationName = "view.select"` narrows to the literal, so it is now `declare const`;
- `as const` made a tuple readonly, so the probe failed for the wrong reason.

Both were found by the mutation checks and fixed.

## Round 30

- **Reviewer:** GPT-6.1-Sol (high effort), independent and read-only. This was the final round
  under the cap.
- **Reviewed:** 3a9770c against 65fb10a.
- **Verdict: NOT READY.** Two class-(A) findings, one major and one minor. Both were fixed in the
  next commit and not reviewed again, under the cap.
- **Confirmed:** every round-29 fix closes its finding:
  - typed extras are refused;
  - direct extra keys are caught, and closed unions are exclusive, through references too;
  - structural siblings and literal types are checked;
  - success-envelope mutations are refused;
  - union names and mismatched envelopes fail to compile.

  Positive probes pass: optional, nullable, nullable literals, annotated and defaulted
  references, records, tuples, union inputs, integer and float literals.

### Findings and fixes

1. **A union-typed argument masked an invalid member (major).** `args: {phi} | {phi; extra}`
   compiled, because `Exact` distributed over the argument type and the valid member satisfied
   the check for both.
   - **Fix:** `Exact<T, A>` is now `false extends ExactOK<T, A> ? never : unknown`. `ExactOK`
     checks each member of `A` on its own: the member must fit some branch of `T`, with no
     undeclared key at any depth.
   - A key whose type is `never` (a `Record<string, never>` member) can hold no value, so it
     counts as absent.
   - **Tests:** in `contract.typetest.ts`, top-level and nested union negatives, a union whose
     members are all valid (accepted), and direct `Exact` checks against records, tuples, optional
     properties and union targets. Each of the reviewer's reproducers (`union-repro.ts`,
     `union-extra.ts`, `union-extra-deep.ts`) is rejected at every call.
2. **The recursive walk was unbounded (minor).** `{ value: JsonValue }` held in a variable hit
   TS2589, "excessively deep". A recursive alias (`JsonTree = str | list[JsonTree]`) failed too.
   - **Fix:** a target that accepts any JSON value needs no check, and `ExactOK` stops there.
   - The generator refuses recursive definitions, direct or indirect (`Unsupported`, naming the
     cycle). `JsonValue` is the one built-in recursive type.
   - **Tests:** Pydantic `JsonTree` and a recursive `Node` model are refused, an indirect cycle is
     refused, an acyclic chain is accepted, and `value: Any` generates `JsonValue` and type-checks,
     both as a variable and as a deep literal.
   - **What remains (B, documented):** recursive models cannot be operation inputs or outputs
     until `Exact` gets a bounded walk.

**Mutation checks:** six mutations, all caught. Two are in the generator (the cycle check),
caught by pytest. Four are in the template, caught by `tsc`: no per-member check, no stop at
`JsonValue`, never-valued keys rejected, undeclared keys allowed.

## Limits carried forward (B)

- Integrality, bounds, patterns and lengths are doc comments only; the server enforces them.
- Outside `callOperation`, TypeScript's structural typing lets a variable carry undeclared keys.
- Recursive definitions (other than `JsonValue`) are refused by the generator.
- `callOperation` trusts the server's reply (a cast, not runtime validation), and a network
  failure rejects, as before.
