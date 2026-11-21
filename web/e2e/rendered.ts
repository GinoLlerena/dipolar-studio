// What the page shows of a fixed-geometry run, checked against a result (round 79, finding 4): an
// API comparison alone passes while the page shows wrong numbers. Each shown number must equal the
// result's within half a unit of its last shown digit.

import type { Locator } from "@playwright/test";
import { expect } from "./harness";

/** The numbers in a shown text ("−0.15987 ± 0.00018", "[0.27966, 0.28037]", "−1,742.6"), each with
 * its number of decimals. */
export function numbersIn(text: string): { value: number; decimals: number }[] {
  const cleaned = text.replace(/−/g, "-").replace(/(\d)[,   ](?=\d{3}\b)/g, "$1");
  return [...cleaned.matchAll(/[-+]?\d+(?:\.(\d+))?(?:e[-+]?\d+)?/g)].map((m) => ({ value: Number(m[0]), decimals: m[1]?.length ?? 0 }));
}

function near(shown: { value: number; decimals: number } | undefined, actual: number | null | undefined, what: string): void {
  expect(shown, `${what}: shown`).toBeDefined();
  expect(actual, `${what}: in the result`).not.toBeNull();
  const half = 0.5 * 10 ** -(shown?.decimals ?? 0);
  expect(Math.abs((shown?.value ?? Number.NaN) - (actual as number)), `${what}: ${shown?.value} vs ${actual}`).toBeLessThanOrEqual(half * (1 + 1e-9));
}

type Component = { name: string; status: string; estimate: number | null; se: number | null; intervals: { level: string; lower: number; upper: number }[] | null };
type Row = { coupling_id: string; multiplicity: number; observed: { value: number }; sigma: { value: number }; predicted: { value: number }; residual: { value: number }; normalized_residual: number };

/** The estimable-combinations panel shows each reported component's estimate, standard error and
 * interval endpoints as the result has them. */
export async function expectComponentsShown(pane: Locator, components: readonly Component[]): Promise<void> {
  const reported = components.filter((c) => c.status !== "fixed-by-symmetry");
  await expect(pane.locator("tr[data-component]")).toHaveCount(reported.length);
  for (const c of reported) {
    const cells = pane.locator(`tr[data-component="${c.name}"] > td`);
    const [estimate, se] = numbersIn((await cells.nth(2).textContent()) ?? "");
    near(estimate, c.estimate, `${c.name} estimate`);
    if (c.se !== null) near(se, c.se, `${c.name} se`);
    if (c.status === "estimated") {
      for (const [k, level] of (["68.3", "95"] as const).entries()) {
        const iv = c.intervals?.find((i) => i.level === level);
        const [lo, hi] = numbersIn((await cells.nth(3 + k).textContent()) ?? "");
        near(lo, iv?.lower, `${c.name} ${level} % lower`);
        near(hi, iv?.upper, `${c.name} ${level} % upper`);
      }
    }
  }
}

/** The residual table shows each row's multiplicity, observed value, σ, prediction, residual and
 * normalized residual as the result has them (columns: label, ×n, D, σ, calc, residual, z). */
export async function expectRowsShown(table: Locator, rows: readonly Row[], labelOf: (id: string) => string): Promise<void> {
  await expect(table.locator("tbody tr")).toHaveCount(rows.length);
  for (const r of rows) {
    const cells = table.locator("tbody tr", { hasText: labelOf(r.coupling_id) }).first().locator("td");
    const shown = async (k: number) => numbersIn((await cells.nth(k).textContent()) ?? "")[0];
    expect((await shown(1))?.value, `${r.coupling_id} multiplicity`).toBe(r.multiplicity);
    near(await shown(2), r.observed.value, `${r.coupling_id} observed`);
    near(await shown(3), r.sigma.value, `${r.coupling_id} σ`);
    near(await shown(4), r.predicted.value, `${r.coupling_id} predicted`);
    near(await shown(5), r.residual.value, `${r.coupling_id} residual`);
    near(await shown(6), r.normalized_residual, `${r.coupling_id} residual/σ`);
  }
}

type Verdict = {
  n_obs: number;
  rank: { required: number; numerical: number; verified: boolean; ratios: number[] };
  adequacy: { chi2: number; nu: number; p_value: number | null; status: string; code: string | null };
  admissibility: { status: string; lambda_min: number | null; certificate: string };
  rms_residual: { value: number };
  symmetry: { point_group: string; tolerance: { value: number }; max_displacement: { value: number }; medium: string };
};

/** The run's verdict as shown (round 80, finding 6): each fact (`[data-fact]`) equals the result's. */
export async function expectVerdictShown(detail: Locator, r: Verdict): Promise<void> {
  const text = async (fact: string) => (await detail.locator(`[data-fact="${fact}"]`).textContent()) ?? "";
  const one = async (fact: string, actual: number | null) => {
    if (actual === null) expect(await text(fact), fact).toContain("—");
    else near(numbersIn(await text(fact))[0], actual, fact);
  };
  await expect(detail.locator("[data-fact]").first()).toBeVisible();
  expect(numbersIn(await text("rank.required"))[0]?.value, "rank.required").toBe(r.rank.required);
  expect(numbersIn(await text("rank.numerical"))[0]?.value, "rank.numerical").toBe(r.rank.numerical);
  const ratios = numbersIn((await text("rank.ratios")).replace(/ × 10([⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+)/g, (_, e: string) => `e${superscript(e)}`));
  expect(ratios.length, "rank.ratios").toBeGreaterThanOrEqual(r.rank.ratios.length);
  await expect(detail.locator(`[data-rank-verified="${r.rank.verified}"]`)).toBeVisible();
  await one("adequacy.chi2", r.adequacy.chi2);
  expect(numbersIn(await text("dof")).map((n) => n.value), "N / d / ν").toEqual([r.n_obs, r.rank.required, r.adequacy.nu]);
  if (r.adequacy.p_value === null || r.adequacy.p_value >= 0.001) await one("adequacy.p_value", r.adequacy.p_value);
  else expect(await text("adequacy.p_value")).toContain("< 0.001");
  expect(await text("adequacy.status"), "adequacy.status").toContain(r.adequacy.code ?? (r.adequacy.status === "given" ? "Adequate" : "Inadequate"));
  await one("rms", r.rms_residual.value);
  expect(await text("admissibility.status"), "admissibility.status").toBe(r.admissibility.status);
  await one("admissibility.lambda_min", r.admissibility.lambda_min);
  expect(await text("admissibility.certificate"), "admissibility.certificate").toBe(r.admissibility.certificate);
  expect(await text("symmetry.point_group"), "symmetry.point_group").toBe(r.symmetry.point_group);
  await one("symmetry.tolerance", r.symmetry.tolerance.value);
  expect(await text("symmetry.medium"), "symmetry.medium").toBe(r.symmetry.medium);
}

const SUPERSCRIPT = "⁰¹²³⁴⁵⁶⁷⁸⁹";
function superscript(digits: string): string {
  return [...digits].map((d) => (d === "⁻" ? "-" : String(SUPERSCRIPT.indexOf(d)))).join("");
}
