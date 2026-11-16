// "The final project and results equal those of the UI path" (04 §7), with quantity-specific
// tolerances (§8.6): the whole of a run, compared field by field (M3 exit audit, round 53: a
// comparison of a few chosen fields let predictions 1 000 Hz off, a flipped validity flag and a
// changed p-value through).
//
// Fail-closed: a number is compared only under an explicit rule for its quantity; any other
// number, a key on one side only, a different array length or type, or a different string,
// boolean or integer is a difference. Pure, with no imports, so tests/compare.test.ts runs it.

/** The frozen regression tolerances, as in datasets/biphenyl-synthetic/expected/spec.json. */
export type Tolerances = {
  predictions_atol_Hz: number;
  phi_atol_deg: number;
  S_atol: number;
  objective_rtol: number;
  phi_interval_endpoint_atol_deg: number;
  S_interval_endpoint_atol: number;
  stderr_rtol: number;
};

/** A run's condition number has no frozen tolerance: it is a diagnostic, compared relatively. */
export const CONDITION_RTOL = 1e-6;

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
type Rule = { abs: number } | { rel: number };

/** The tolerance of a parameter's value (θ, order parameters and their interval estimates). */
function parameter(name: string, t: Tolerances): Rule | null {
  if (name === "phi_deg") return { abs: t.phi_atol_deg };
  if (name === "Szz" || name === "Delta" || name === "Sxy") return { abs: t.S_atol };
  return null;
}

function endpoint(name: string, t: Tolerances): Rule | null {
  if (name === "phi_deg") return { abs: t.phi_interval_endpoint_atol_deg };
  if (name === "Szz" || name === "Delta" || name === "Sxy") return { abs: t.S_interval_endpoint_atol };
  return null;
}

/** The rule for the number at `path` (keys and `[]` for array items; `owner` is the object that
 * holds it, for the parameter's name or the coupling's σ), or null when there is none. */
function rule(path: string, owner: { [key: string]: Json }, result: { [key: string]: Json }, t: Tolerances): Rule | null {
  const name = typeof owner.name === "string" ? owner.name : typeof owner.parameter === "string" ? owner.parameter : "";
  switch (path) {
    case "theta[].value":
    case "order[].value":
    case "basins[].theta[].value":
    case "intervals[].estimate":
      return parameter(name, t);
    case "intervals[].lower":
    case "intervals[].upper":
      return endpoint(name, t);
    case "stderr[].value":
      return { rel: t.stderr_rtol };
    case "chi2":
    case "p_value":
    case "basins[].chi2":
      return { rel: t.objective_rtol };
    case "basins[].delta_chi2": // a difference of χ² values: absolute, at the objective's scale
      return { abs: t.objective_rtol * Math.max(1, typeof result.chi2 === "number" ? result.chi2 : 1) };
    case "couplings[].calculated.value":
    case "couplings[].residual.value":
    case "rms_residual.value":
      return { abs: t.predictions_atol_Hz };
    case "couplings[].normalized_residual": {
      const sigma = owner.sigma as { value?: Json } | undefined;
      return typeof sigma?.value === "number" && sigma.value > 0 ? { abs: t.predictions_atol_Hz / sigma.value } : null;
    }
    case "validity.inner_condition_number":
      return { rel: CONDITION_RTOL };
    // Inputs copied into the result: equal exactly.
    case "couplings[].observed.value":
    case "couplings[].sigma.value":
    case "model.phi_domain[].value":
    case "numerical_context.admissibility_atol":
    case "numerical_context.rank_rtol":
      return { abs: 0 };
    default:
      return null;
  }
}

function within(a: number, b: number, r: Rule): boolean {
  const d = Math.abs(a - b);
  return "abs" in r ? d <= r.abs : d <= r.rel * Math.max(Math.abs(a), Math.abs(b));
}

/** Every difference between two run results (`run.get`'s `result`), or none. */
export function resultDifferences(a: Json, b: Json, t: Tolerances): string[] {
  const out: string[] = [];
  const top = (a !== null && typeof a === "object" && !Array.isArray(a) ? a : {}) as { [key: string]: Json };
  const walk = (x: Json, y: Json, path: string, shown: string, owner: { [key: string]: Json }) => {
    if (Array.isArray(x) || Array.isArray(y)) {
      if (!Array.isArray(x) || !Array.isArray(y) || x.length !== y.length) {
        out.push(`${shown}: different arrays`);
        return;
      }
      x.forEach((v, i) => walk(v, y[i] as Json, `${path}[]`, `${shown}[${i}]`, owner));
      return;
    }
    if (x !== null && typeof x === "object") {
      if (y === null || typeof y !== "object") {
        out.push(`${shown}: an object and ${JSON.stringify(y)}`);
        return;
      }
      const keys = new Set([...Object.keys(x), ...Object.keys(y)]);
      for (const k of keys) {
        if (!(k in x) || !(k in y)) out.push(`${shown}.${k}: on one side only`);
        else walk(x[k] as Json, y[k] as Json, path === "" ? k : `${path}.${k}`, `${shown}.${k}`, x);
      }
      return;
    }
    if (typeof x === "number" && typeof y === "number") {
      const r = rule(path, owner, top, t);
      if (r !== null) {
        if (!within(x, y, r)) out.push(`${shown}: ${x} and ${y} (${JSON.stringify(r)})`);
      } else if (!(Number.isInteger(x) && Number.isInteger(y))) {
        out.push(`${shown}: no tolerance rule for this quantity`);
      } else if (x !== y) {
        out.push(`${shown}: ${x} and ${y}`); // counts and ranks: exactly
      }
      return;
    }
    if (x !== y) out.push(`${shown}: ${JSON.stringify(x)} and ${JSON.stringify(y)}`);
  };
  walk(a, b, "", "result", top);
  return out;
}
