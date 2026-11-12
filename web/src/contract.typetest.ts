// Type-level tests of the generated contract (M2 step 1b). Nothing imports this file, so it is not
// bundled; `tsc` checks it. Each `@ts-expect-error` line must fail to compile: if a generated type
// became looser than the registry's schema, tsc would report the directive as unused.

import { callOperation } from "./api";
import type {
  DescribeProjectOut,
  Envelope,
  ErrorCode,
  OperationInput,
  OperationName,
  OperationOutput,
  SuccessEnvelope,
} from "./generated/contract";
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

// ---------------------------------------------------------------- the call boundary (round 29)
// Never called: these lines only have to compile, or fail to compile.
export async function callBoundary(token: string, flip: boolean): Promise<void> {
  // A variable (not a fresh literal) with exactly the declared keys is accepted …
  const args = { phi: { value: 37, unit: "deg" as const } };
  await callOperation("fit.preview", args, token);
  const domain = [
    { value: 0, unit: "deg" as const },
    { value: 90, unit: "deg" as const },
  ] as [{ value: number; unit: "deg" }, { value: number; unit: "deg" }];
  const model = { kind: "rigid", order: "c1", frame: "input", phi_domain: domain, expected_science_revision: 0 } as const;
  await callOperation("model.set", model, token);
  const mapping = { H2: "spn_000001" };
  await callOperation("couplings.import", { csv: "", confirmed_mapping: mapping, expected_science_revision: 0 }, token);

  // … but extra keys fail even when they ride on a variable, at any depth.
  const extra = { phi: { value: 37, unit: "deg" as const }, extra: 1 };
  // @ts-expect-error: `extra` is not an argument of fit.preview
  await callOperation("fit.preview", extra, token);
  const nested = { phi: { value: 37, unit: "deg" as const, extra: 1 } };
  // @ts-expect-error: `phi.extra` is not part of Degrees
  await callOperation("fit.preview", nested, token);
  const element: [{ value: number; unit: "deg"; extra: number }, { value: number; unit: "deg" }] = [
    { value: 0, unit: "deg", extra: 1 },
    { value: 90, unit: "deg" },
  ];
  // @ts-expect-error: a tuple element with an extra key
  await callOperation("model.set", { ...model, phi_domain: element }, token);
  const empty = { anything: 1 };
  // @ts-expect-error: an argument-free operation takes no keys (its type alone already says so)
  await callOperation("render.describe_view", empty, token);

  // One operation per call: a union of names cannot pair with either operation's arguments.
  const name = flip ? "fit.preview" : "view.select";
  // @ts-expect-error: the name is a union
  await callOperation(name, { ids: [] }, token);
  const anyName = wideName;
  // @ts-expect-error: the name is any operation
  await callOperation(anyName, { ids: [] }, token);
  // @ts-expect-error: the arguments of another operation
  await callOperation("fit.preview", { ids: [] }, token);

  // The result type follows the one name.
  const envelope = await callOperation("view.select", { ids: [] }, token);
  if (envelope.ok) {
    type _sel = Expect<Equal<typeof envelope.result, OperationOutput<"view.select">>>;
  }
}

declare const wideName: OperationName;

// A union envelope keeps each operation with its own result.
declare const preview: OperationOutput<"fit.preview">;
// @ts-expect-error: operation "view.select" paired with fit.preview's result
const mismatched: SuccessEnvelope<"fit.preview" | "view.select"> = { ok: true, operation: "view.select", result: preview, revisions: { science: 0, workspace: 0 } };
void mismatched;
// @ts-expect-error: the default envelope (all operations) is just as strict
const mismatchedAll: Envelope = { ok: true, operation: "view.select", result: preview, revisions: { science: 0, workspace: 0 } };
void mismatchedAll;

// Unions of closed objects are exclusive: a value may not mix two branches' keys. A fresh literal
// is already caught by the `kind` discriminant; a value held in a variable needs the generated
// `?: never` keys.
declare const template: Extract<DescribeProjectOut["geometry"], { kind: "template" }>;
const geometryOk: DescribeProjectOut["geometry"] = template;
void geometryOk;
const mixed = { ...template, atoms: [] };
// @ts-expect-error: a template geometry carrying the imported branch's `atoms`
const geometryMixed: DescribeProjectOut["geometry"] = mixed;
void geometryMixed;
