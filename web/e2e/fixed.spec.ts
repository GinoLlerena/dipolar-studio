// The page for fixed-geometry projects (Phase 2 V1.4, docs/phase2/v1.4-browser.md E-2 to E-4): the
// Fit workspace without φ and its estimable combinations, the unverified case and the Cs
// suggestion, and the one-ring Structure view. Set-up goes through the API (the robot); what is
// checked is what the page shows.

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import type { Page } from "@playwright/test";
import { expect, openTab, type Server, test } from "./harness";

const ROOT = resolve(import.meta.dirname, "../..");
const DATA = join(ROOT, "datasets", "dichlorobenzene-synthetic");
const FIXED = { kind: "fixed", order: "point-group", frame: "symmetry" };

const pane = (app: Page, id: string) => app.locator(`#${id}`).locator("xpath=ancestor::section");

async function fit(server: Server): Promise<string> {
  const rev = await server.revision();
  const job = (await server.ok("robot", "fit.run", { expected_science_revision: rev })).job.id as string;
  await expect.poll(async () => (await server.ok("robot", "job.status", { job_id: job })).job.status, { timeout: 60_000 }).toBe("succeeded");
  return (await server.ok("robot", "render.describe_view")).run.run_id as string;
}

/** The tutorial's project through the API: D2h, fixed, the three rows. */
async function dichlorobenzene(server: Server): Promise<void> {
  const xyz = readFileSync(join(DATA, "dichlorobenzene.xyz"), "utf-8");
  const csv = readFileSync(join(DATA, "couplings.csv"), "utf-8");
  await server.ok("robot", "project.import_xyz", { xyz, name: "dichlorobenzene", expected_science_revision: 0 });
  await server.ok("robot", "molecule.set_symmetry", { symmetry: { point_group: "D2h" }, expected_science_revision: 1 });
  await server.ok("robot", "model.set", { ...FIXED, expected_science_revision: 2 });
  const names = (xyz.split("\n")[1] ?? "").split("atoms:")[1]?.trim().split(/\s+/) ?? [];
  const spins = (await server.ok("robot", "project.describe")).spins as { id: string; atom: number }[];
  const mapping = Object.fromEntries(["H2", "H3", "H5", "H6"].map((l) => [l, spins.find((s) => s.atom === names.indexOf(l))?.id ?? ""]));
  await server.ok("robot", "couplings.import", { csv, confirmed_mapping: mapping, expected_science_revision: 3 });
}

/** Benzene in its D6h frame (z normal), carbons then protons H7 … H12, as an XYZ file. */
function benzeneXyz(): string {
  const lines = ["12", "benzene"];
  for (const [element, r] of [
    ["C", 1.3914],
    ["H", 1.3914 + 1.0802],
  ] as const) {
    for (let k = 0; k < 6; k++) {
      const a = (Math.PI / 3) * k;
      lines.push(`${element} ${r * Math.cos(a)} ${r * Math.sin(a)} 0`);
    }
  }
  return `${lines.join("\n")}\n`;
}

test("the Fit workspace shows a fixed run's estimable combinations, without φ", async ({ app, server }) => {
  await dichlorobenzene(server);
  const runId = await fit(server);
  await openTab(app, "Fit");
  // No torsion: no preview slider, no landscape, no interval option (exact intervals always).
  await expect(app.locator("#phi-slider")).toHaveCount(0);
  await expect(app.locator("#pane-preview")).toHaveCount(0);
  await expect(app.getByLabel("Profile intervals (slower)")).toHaveCount(0);
  await expect(pane(app, "pane-run")).toContainText("Exact intervals");
  const detail = pane(app, "pane-run-detail");
  await expect(detail).toContainText(runId);
  // The estimable combinations: Szz and Sxx − Syy, each with its estimate and both intervals.
  const estimable = pane(app, "pane-estimable");
  for (const name of ["Szz", "Sxx-Syy"]) {
    const row = estimable.locator(`tr[data-component="${name}"]`);
    await expect(row).toHaveAttribute("data-status", "estimated");
    await expect(row.locator("td.interval")).toHaveCount(2);
  }
  await expect(estimable.locator('tr[data-component="Szz"]')).toContainText("−0.15987 ± 0.00018");
  // Fixed by symmetry, apart: zero by the declaration.
  await expect(estimable.locator('[data-status="fixed-by-symmetry"]')).toHaveCount(3);
  for (const name of ["Sxy", "Sxz", "Syz"]) await expect(estimable.locator(`[data-component="${name}"][data-status="fixed-by-symmetry"]`)).toHaveCount(1);
  // The verdict, as the result states it.
  await expect(detail.locator(".chip", { hasText: "Adequate (p = 0.124)" })).toBeVisible();
  await expect(detail.locator(".chip", { hasText: "Physically admissible" })).toBeVisible();
  await expect(detail.locator('[data-rank-verified="true"]')).toBeVisible();
  await expect(detail).toContainText("D2h");
  // The residuals: one row per observed pair orbit, with its multiplicity.
  const table = pane(app, "pane-residuals").locator("table");
  await expect(table.locator("tbody tr")).toHaveCount(3);
  for (const row of await table.locator("tbody tr").all()) await expect(row).toContainText("×2");
});

test("a planar ring declared C1 is unverified, and the page suggests Cs", async ({ app, server }) => {
  await server.ok("robot", "project.import_xyz", { xyz: benzeneXyz(), name: "benzene", expected_science_revision: 0 });
  await server.ok("robot", "molecule.set_symmetry", { symmetry: { point_group: "C1" }, expected_science_revision: 1 });
  await server.ok("robot", "model.set", { ...FIXED, expected_science_revision: 2 });
  const csv = "spin_a,spin_b,D_obs_Hz,sigma_Hz\nH7,H8,-1200.5,0.5\nH7,H9,-230.1,0.5\nH7,H10,-150.2,0.5\n";
  const { proposed_mapping } = await server.ok("robot", "couplings.reconcile", { csv });
  await server.ok("robot", "couplings.import", { csv, confirmed_mapping: proposed_mapping, expected_science_revision: 3 });
  await fit(server);
  await openTab(app, "Fit");
  const estimable = pane(app, "pane-estimable");
  await expect(estimable.locator('tr[data-status="projected"]').first()).toBeVisible();
  await expect(estimable).toContainText("not supported: rank unverified");
  await expect(estimable.locator('tr[data-status="estimated"]')).toHaveCount(0);
  const detail = pane(app, "pane-run-detail");
  await expect(detail.locator('[data-rank-verified="false"]')).toBeVisible();
  await expect(detail).toContainText("ADEQUACY_RANK_UNVERIFIED");

  // The Data workspace suggests Cs (the server's suggestion, not validated until declared).
  await openTab(app, "Data");
  const symmetry = pane(app, "pane-symmetry");
  await expect(symmetry).toContainText("Declared: C1");
  await expect(symmetry.getByRole("note").filter({ hasText: "lie in one plane" })).toBeVisible();
  await symmetry.getByRole("button", { name: "Use this suggestion" }).click();
  await expect(symmetry.locator("#symmetry-group")).toHaveValue("Cs");
  await expect(server.ok("robot", "molecule.declarations").then((d) => d.symmetry.point_group)).resolves.toBe("C1"); // only filled
  await symmetry.getByRole("button", { name: "Declare symmetry" }).click();
  await expect.poll(async () => (await server.ok("robot", "molecule.declarations")).symmetry.point_group).toBe("Cs");
  await expect(symmetry).toContainText("Declared: Cs");
  await expect(symmetry.getByRole("note").filter({ hasText: "lie in one plane" })).toHaveCount(0);
});

test("the Structure view of a fixed project: no torsion, the symmetry frame, every orbit member", async ({ app, server }) => {
  await dichlorobenzene(server);
  await fit(server);
  await openTab(app, "Structure");
  const svg = app.locator("svg.scene");
  await expect(svg).toHaveAttribute("aria-label", /D2h/);
  expect(await svg.getAttribute("aria-label")).not.toContain("φ");
  for (const axis of ["x", "y", "z"]) await expect(svg.locator(`.sym-axis[data-axis="${axis}"]`)).toHaveCount(1);
  const couplings = (await server.ok("robot", "project.describe")).couplings as { id: string }[];
  for (const c of couplings) await expect(svg.locator(`path.arc[data-id="${c.id}"]`)).toHaveCount(2);
  // Picking a symmetry copy selects its row, and the row's whole orbit is drawn selected.
  const target = couplings[2]!.id;
  await svg.locator(`path.arc[data-id="${target}"][data-copy="1"]`).dispatchEvent("click");
  await expect.poll(async () => (await server.ok("robot", "render.describe_view")).selection.map((s: { id: string }) => s.id)).toEqual([target]);
  await expect(svg.locator(`path.arc.is-selected[data-id="${target}"]`)).toHaveCount(2);
  await expect(svg.locator("path.arc.is-selected")).toHaveCount(2);
});

test("the model inspector enters and leaves the fixed-geometry fit", async ({ app, server }) => {
  await server.ok("robot", "project.import_xyz", { xyz: benzeneXyz(), name: "benzene", expected_science_revision: 0 });
  await openTab(app, "Data");
  const symmetry = pane(app, "pane-symmetry");
  await symmetry.locator("#symmetry-group").selectOption("D6h");
  await symmetry.getByRole("button", { name: "Declare symmetry" }).click();
  await expect(symmetry).toContainText("Declared: D6h");
  await app.locator("#model-kind").selectOption("fixed");
  await app.getByRole("button", { name: "Apply" }).click();
  await expect.poll(async () => (await server.ok("robot", "project.describe")).model.kind).toBe("fixed");
  await expect(app.getByLabel("φ domain (°) from")).toHaveCount(0);
  // Leaving it asks for a torsion domain again.
  await app.locator("#model-kind").selectOption("rigid");
  await expect(app.getByLabel("φ domain (°) from")).toBeVisible();
  await app.locator("#model-order").selectOption("c1");
  await app.locator("#model-frame").selectOption("input");
  await app.getByLabel("φ domain (°) from").fill("-180");
  await app.getByLabel("φ domain (°) to").fill("180");
  await app.getByRole("button", { name: "Apply" }).click();
  await expect.poll(async () => (await server.ok("robot", "project.describe")).model.kind).toBe("rigid");
  // A declared symmetry cannot be cleared under the fixed fit; here it can.
  await symmetry.getByRole("button", { name: "Clear" }).click();
  await expect.poll(async () => (await server.ok("robot", "molecule.declarations")).symmetry).toBeNull();
});
