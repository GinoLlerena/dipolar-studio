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
