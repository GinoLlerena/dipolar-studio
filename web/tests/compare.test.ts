// The tutorial's result comparison (e2e/compare.ts) is not vacuous: every altered field of a run's
// result is a difference (M3 exit audit, round 53).
import assert from "node:assert/strict";
import test from "node:test";
import { resultDifferences, type Tolerances } from "../e2e/compare.ts";

const TOL: Tolerances = {
  predictions_atol_Hz: 1e-6,
  phi_atol_deg: 1e-4,
  S_atol: 1e-6,
  objective_rtol: 1e-6,
  phi_interval_endpoint_atol_deg: 1e-4,
  S_interval_endpoint_atol: 1e-6,
  stderr_rtol: 1e-3,
};

const coupling = (id: string, calc: number) => ({
  id,
  label: `H${id}`,
  observed: { value: 100, unit: "Hz" },
  sigma: { value: 0.5, unit: "Hz" },
  calculated: { value: calc, unit: "Hz" },
  residual: { value: 100 - calc, unit: "Hz" },
  normalized_residual: (100 - calc) / 0.5,
});

function result(): any {
  return {
    adequate: true,
    basins: [{ chi2: 12.4, delta_chi2: 0, theta: [{ name: "phi_deg", value: -36.98 }] }],
    chi2: 12.4,
    couplings: [coupling("cpl_1", 99.5), coupling("cpl_2", 100.7)],
    estimand: "fixed-labels torsion",
    fit_version: "varpro-trf.9",
    intervals: [
      { parameter: "phi_deg", kind: "profile", label: "φ", estimate: -36.98, lower: -37.01, upper: -36.96, supported: true, note: "" },
      { parameter: "Szz", kind: "profile", label: "Szz", estimate: 0.25, lower: 0.2499, upper: 0.2501, supported: true, note: "" },
    ],
    model: { kind: "rigid", order: "c2z", frame: "input", phi_domain: [{ value: -90, unit: "deg" }, { value: 0, unit: "deg" }] },
    n_obs: 14,
    nu: 10,
    numerical_context: { admissibility_atol: 1e-9, rank_rtol: 1e-10, forward_model: "f1" },
    order: [{ name: "Szz", value: 0.25 }, { name: "Delta", value: 0.0304 }, { name: "Sxy", value: 0.0001 }],
    p_free: 4,
    p_value: 0.26,
    rms_residual: { value: 0.53, unit: "Hz" },
    stderr: [{ name: "phi_deg", value: 0.012 }],
    theta: [{ name: "phi_deg", value: -36.98 }],
    validity: { converged: true, regular: true, inner_condition_number: 12.3, inner_rank: 3, physically_admissible: true },
  };
}

test("an equal result, and one within the tolerances, has no difference", () => {
  assert.deepEqual(resultDifferences(result(), result(), TOL), []);
  const near = result();
  near.theta[0].value += 5e-5; // within φ's 1e-4°
  near.couplings[0].calculated.value += 5e-7; // within 1e-6 Hz
  near.chi2 *= 1 + 5e-7;
  near.stderr[0].value *= 1 + 5e-4;
  assert.deepEqual(resultDifferences(result(), near, TOL), []);
});

test("every altered field is a difference", () => {
  const changes: [string, (r: any) => void][] = [
    // Round 53's mutant: these passed the old comparison.
    ["predictions +1000 Hz", (r) => r.couplings.forEach((c: any) => (c.calculated.value += 1000))],
    ["validity.regular flipped", (r) => (r.validity.regular = !r.validity.regular)],
    ["adequacy flipped", (r) => (r.adequate = !r.adequate)],
    ["p-value doubled", (r) => (r.p_value *= 2)],
    // And every other kind of field.
    ["φ", (r) => (r.theta[0].value += 2e-4)],
    ["an order parameter", (r) => (r.order[1].value += 2e-6)],
    ["a standard error", (r) => (r.stderr[0].value *= 1.01)],
    ["χ²", (r) => (r.chi2 *= 1 + 2e-6)],
    ["a residual", (r) => (r.couplings[1].residual.value += 2e-6)],
    ["a normalized residual", (r) => (r.couplings[1].normalized_residual += 1e-5)],
    ["an observed value", (r) => (r.couplings[0].observed.value += 1e-9)],
    ["an interval endpoint", (r) => (r.intervals[0].upper += 2e-4)],
    ["an interval's support", (r) => (r.intervals[1].supported = false)],
    ["a basin", (r) => (r.basins[0].theta[0].value += 1)],
    ["ν", (r) => (r.nu += 1)],
    ["a rank", (r) => (r.validity.inner_rank -= 1)],
    ["the condition number", (r) => (r.validity.inner_condition_number *= 1.001)],
    ["the estimand", (r) => (r.estimand = "acute torsion")],
    ["a label", (r) => (r.couplings[0].label = "H9")],
    ["a coupling missing", (r) => r.couplings.pop()],
    ["a field on one side only", (r) => (r.extra = true)],
    ["a number without a tolerance rule", (r) => (r.validity.new_measure = 0.5)],
  ];
  for (const [name, change] of changes) {
    const altered = result();
    change(altered);
    assert.notDeepEqual(resultDifferences(result(), altered, TOL), [], name);
  }
});

test("a number without a rule is a difference even when equal on both sides (fail-closed)", () => {
  const a = result();
  a.validity.new_measure = 0.5;
  const b = result();
  b.validity.new_measure = 0.5;
  assert.match(resultDifferences(a, b, TOL).join("\n"), /no tolerance rule/);
});

// ------------------------------------------------------------------ V1.4: fixed-geometry runs
// The fixed-geometry tutorial compares FixedRunOut results (docs/phase2/v1.4-browser.md E-6) with
// its own frozen tolerances (datasets/dichlorobenzene-synthetic/expected/spec.json), fail-closed.
import { readFileSync } from "node:fs";
import { fixedResultDifferences, type FixedTolerances } from "../e2e/compare.ts";

const FIXED_TOL: FixedTolerances = (
  JSON.parse(readFileSync(new URL("../../datasets/dichlorobenzene-synthetic/expected/spec.json", import.meta.url), "utf-8")) as {
    tolerances: { regression: FixedTolerances };
  }
).tolerances.regression;
/** A real result: the tutorial's run (contract 0.11.0's FixedRunOut). */
const fixedRun = (): any => JSON.parse(readFileSync(new URL("./data/fixed-run.json", import.meta.url), "utf-8"));

test("an equal fixed result, and one within the tolerances, has no difference", () => {
  assert.deepEqual(fixedResultDifferences(fixedRun(), fixedRun(), FIXED_TOL), []);
  const near = fixedRun();
  near.components[0].estimate += 5e-10;
  near.components[1].intervals[1].upper -= 5e-10;
  near.components[0].se *= 1 + 5e-7;
  near.rows[2].predicted.value += 5e-7;
  near.rows[2].residual.value -= 5e-7;
  near.adequacy.chi2 *= 1 + 5e-7;
  near.rank.ratios[1] *= 1 + 5e-10;
  near.covariance_b.matrix[0][1] *= 1 + 5e-7;
  assert.deepEqual(fixedResultDifferences(fixedRun(), near, FIXED_TOL), []);
});

/** Every leaf of a JSON value, by path. */
function leaves(value: any, path: (string | number)[] = []): (string | number)[][] {
  if (value !== null && typeof value === "object") {
    const keys = Array.isArray(value) ? value.map((_, i) => i) : Object.keys(value);
    const inner = keys.flatMap((k) => leaves(value[k], [...path, k]));
    return inner.length ? inner : [path];
  }
  return [path];
}

test("every altered leaf of a fixed result is a difference (mutation over the whole result)", () => {
  const paths = leaves(fixedRun());
  assert.ok(paths.length > 150, `${paths.length} leaves`);
  for (const path of paths) {
    const altered = fixedRun();
    const owner = path.slice(0, -1).reduce((o: any, k) => o[k], altered);
    const key = path[path.length - 1] as string | number;
    const v = owner[key];
    if (typeof v === "number") owner[key] = v + Math.max(1e-3, Math.abs(v) * 1e-3);
    else if (typeof v === "string") owner[key] = `${v}·`;
    else if (typeof v === "boolean") owner[key] = !v;
    else if (v === null) owner[key] = 0;
    else if (Array.isArray(v)) owner[key] = [0];
    else owner[key] = { extra: 0 };
    assert.notDeepEqual(fixedResultDifferences(fixedRun(), altered, FIXED_TOL), [], path.join("."));
  }
});

test("a fixed result's shape changes are differences", () => {
  const changes: [string, (r: any) => void][] = [
    ["a row missing", (r) => r.rows.pop()],
    ["a component missing", (r) => r.components.pop()],
    ["a field on one side only", (r) => (r.extra = true)],
    ["a number without a tolerance rule", (r) => (r.rank.new_measure = 0.5)],
    ["a search result in its place", (r) => (r.theta = [{ name: "phi_deg", value: 0 }])],
  ];
  for (const [name, change] of changes) {
    const altered = fixedRun();
    change(altered);
    assert.notDeepEqual(fixedResultDifferences(fixedRun(), altered, FIXED_TOL), [], name);
  }
});

test("a search-era result is not compared under the fixed rules, nor the reverse", () => {
  assert.notDeepEqual(fixedResultDifferences(result(), result(), FIXED_TOL), []);
  assert.notDeepEqual(resultDifferences(fixedRun(), fixedRun(), TOL), []);
});

// ------------------------------------------------------------------ round 79
test("round 79: a number without a rule in a fixed result is a difference, integer or not", () => {
  for (const [name, value] of [
    ["an unknown integer", 1],
    ["an unknown float", 0.5],
  ] as const) {
    const a = fixedRun();
    const b = fixedRun();
    a.rank.new_measure = value;
    b.rank.new_measure = value;
    assert.match(fixedResultDifferences(a, b, FIXED_TOL).join("\n"), /no tolerance rule/, name);
  }
  const a = fixedRun();
  const b = fixedRun();
  a.provenance.numerical_context.new_atol = 1e-9;
  b.provenance.numerical_context.new_atol = 1e-9;
  assert.match(fixedResultDifferences(a, b, FIXED_TOL).join("\n"), /no tolerance rule/, "an unknown numerical-context number");
});

test("round 79: a one-sided key named like an inherited property is a difference", () => {
  const withProto = (text: string, key: string) => JSON.parse(text.replace(`"${key}":{`, `"${key}":{"__proto__":{},`));
  const fixedText = JSON.stringify(fixedRun());
  assert.notDeepEqual(fixedResultDifferences(fixedRun(), withProto(fixedText, "adequacy"), FIXED_TOL), []);
  assert.notDeepEqual(fixedResultDifferences(withProto(fixedText, "adequacy"), fixedRun(), FIXED_TOL), []);
  const searchText = JSON.stringify(result());
  assert.notDeepEqual(resultDifferences(result(), withProto(searchText, "validity"), TOL), []);
  const constructor = JSON.parse(searchText.replace('"validity":{', '"validity":{"constructor":1,'));
  assert.notDeepEqual(resultDifferences(constructor, result(), TOL), []);
});
