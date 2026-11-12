// Type-level tests of the generated contract (M2 step 1b). Nothing imports this file, so it is not
// bundled; `tsc` checks it. Each `@ts-expect-error` line must fail to compile: if a generated type
// became looser than the registry's schema, tsc would report the directive as unused.

import type { Envelope, ErrorCode, OperationInput, OperationName, OperationOutput } from "./generated/contract";
import { CONTRACT_VERSION, OPERATIONS } from "./generated/contract";

type Expect<T extends true> = T;
type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false;

// Valid arguments compile.
void ({ phi: { value: 37, unit: "deg" } } satisfies OperationInput<"fit.preview">);
void ({} satisfies OperationInput<"fit.run">);
void ({ intervals: true } satisfies OperationInput<"fit.run">);
void ({} satisfies OperationInput<"render.describe_view">);

// @ts-expect-error: unknown operation name
void ({} satisfies OperationInput<"fit.nonexistent">);
// @ts-expect-error: wrong unit literal
void ({ phi: { value: 37, unit: "rad" } } satisfies OperationInput<"fit.preview">);
// @ts-expect-error: missing required property
void ({} satisfies OperationInput<"fit.preview">);
// @ts-expect-error: unknown property (additionalProperties: false)
void ({ phi: { value: 37, unit: "deg" }, extra: 1 } satisfies OperationInput<"fit.preview">);
// @ts-expect-error: an operation without arguments takes the empty object only
void ({ anything: 1 } satisfies OperationInput<"render.describe_view">);
// @ts-expect-error: a string where a number is required
void ({ phi: { value: "37", unit: "deg" } } satisfies OperationInput<"fit.preview">);
// @ts-expect-error: optional, but never explicitly undefined (exactOptionalPropertyTypes)
void ({ intervals: undefined } satisfies OperationInput<"fit.run">);
// @ts-expect-error: phi_domain is a fixed-length pair
void ({ kind: "rigid", order: "c1", frame: "input", phi_domain: [{ value: 0, unit: "deg" }], expected_science_revision: 0 } satisfies OperationInput<"model.set">);
// @ts-expect-error: enum values only
void ({ kind: "rigid", order: "c3", frame: "input", phi_domain: [{ value: 0, unit: "deg" }, { value: 90, unit: "deg" }], expected_science_revision: 0 } satisfies OperationInput<"model.set">);

// Results are typed per operation, and success narrows on `ok`.
declare const envelope: Envelope<"fit.preview">;
if (envelope.ok) {
  type _result = Expect<Equal<typeof envelope.result, OperationOutput<"fit.preview">>>;
  const hz: "Hz" = envelope.result.rms_residual.unit;
  void hz;
  // @ts-expect-error: fit.preview's result has no p_value (fit.run's does)
  void envelope.result.p_value;
} else {
  type _code = Expect<Equal<typeof envelope.error.code, ErrorCode>>;
  // @ts-expect-error: error codes are a closed set
  const code: typeof envelope.error.code = "NOT_A_CODE";
  void code;
}

// Every operation has metadata, and the metadata is literal.
type _names = Expect<Equal<keyof typeof OPERATIONS, OperationName>>;
type _kind = Expect<Equal<(typeof OPERATIONS)["fit.preview"]["kind"], "query">>;
const version: string = CONTRACT_VERSION;
void version;
