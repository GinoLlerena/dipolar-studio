// What the page shows of a fixed-geometry run, checked against a result (round 79, finding 4): an
// API comparison alone passes while the page shows wrong numbers. Each shown number must equal the
// result's within half a unit of its last shown digit.

import type { Locator } from "@playwright/test";
import { expect } from "./harness";

/** The numbers in a shown text ("−0.15987 ± 0.00018", "[0.27966, 0.28037]", "−1,742.6"), each with
 * its number of decimals. */
export function numbersIn(text: string): { value: number; decimals: number }[] {
  const cleaned = text.replace(/−/g, "-").replace(/(\d)[,   ](?=\d{3}\b)/g, "$1");
  return [...cleaned.matchAll(/[-+]?\d+(?:\.(\d+))?/g)].map((m) => ({ value: Number(m[0]), decimals: m[1]?.length ?? 0 }));
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
