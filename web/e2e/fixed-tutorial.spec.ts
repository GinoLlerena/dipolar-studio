// The fixed-geometry tutorial (Phase 2 V1.4, docs/phase2/v1.4-browser.md E-6): synthetic
// 1,4-dichlorobenzene, the same steps through the page and by the robot
// (tools/robot/robot.py --scenario fixed-tutorial: HTTP registry calls only, in a clean
// `python -I` process), each on its own server. The science hash, the exported project, the
// selection and the whole run (every field, fail-closed, with the dataset's frozen tolerances:
// e2e/compare.ts fixedResultDifferences) are compared.

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import type { Page } from "@playwright/test";
import { type FixedTolerances, fixedResultDifferences } from "./compare";
import { expect, openTab, type Server, startServer, test } from "./harness";
import { expectComponentsShown, expectRowsShown, expectVerdictShown } from "./rendered";

const ROOT = resolve(import.meta.dirname, "../..");
const DATA = join(ROOT, "datasets", "dichlorobenzene-synthetic");
const XYZ = join(DATA, "dichlorobenzene.xyz");
const CSV = join(DATA, "couplings.csv");
const PYTHON = process.env.DIPOLAR_ROBOT_PYTHON ?? "python3";
const TOLERANCES = (JSON.parse(readFileSync(join(DATA, "expected", "spec.json"), "utf-8")) as { tolerances: { regression: FixedTolerances } })
  .tolerances.regression;

function robotReport(server: Server): Record<string, any> {
  let out: string;
  try {
    out = execFileSync(
      PYTHON,
      ["-I", join(ROOT, "tools", "robot", "robot.py"), "--ready-file", join(server.dir, "ready.json"), "--scenario", "fixed-tutorial", "--xyz", XYZ, "--csv", CSV],
      { encoding: "utf-8", timeout: 600_000 },
    );
  } catch (error) {
    const e = error as { stdout?: string; stderr?: string; message: string };
    throw new Error(`the robot failed: ${e.stdout?.trim() || e.message}\n${e.stderr?.trim() ?? ""}`);
  }
  const parsed = JSON.parse(out) as Record<string, any>;
  if (!parsed.ok) throw new Error(`the robot failed: ${parsed.error}`);
  return parsed;
}

/** The mapping a user confirms: the file's labels to the imported protons, by the atom names in
 * the XYZ comment line and each spin's atom index (as the robot does). */
async function confirmedMapping(server: Server): Promise<Record<string, string>> {
  const names = (readFileSync(XYZ, "utf-8").split("\n")[1] ?? "").split("atoms:")[1]?.trim().split(/\s+/) ?? [];
  const spins = (await server.ok("user", "project.describe")).spins as { id: string; atom: number }[];
  return Object.fromEntries(["H2", "H3", "H5", "H6"].map((l) => [l, spins.find((s) => s.atom === names.indexOf(l))?.id ?? ""]));
}

const pane = (app: Page, id: string) => app.locator(`#${id}`).locator("xpath=ancestor::section");

test("the fixed-geometry tutorial through the page equals the robot's", async ({ app, server }) => {
  test.setTimeout(240_000);
  // 1. Create the project from the user's geometry.
  await openTab(app, "Data");
  await app.locator("label.button", { hasText: "Import XYZ geometry…" }).locator("input[type=file]").setInputFiles(XYZ);
  await expect(app.locator(".crumb-name")).toHaveText("dichlorobenzene");

  // 2. Declare the symmetry: D2h in the input frame (the form's defaults), 0.01 Å.
  const symmetry = pane(app, "pane-symmetry");
  await symmetry.locator("#symmetry-group").selectOption("D2h");
  await expect(symmetry.locator("#symmetry-tolerance")).toHaveValue("0.01");
  await symmetry.getByRole("button", { name: "Declare symmetry" }).click();
  await expect(app.locator(".crumb .muted")).toContainText("rev 2 ");
  await expect(symmetry).toContainText("Declared: D2h");

  // 3. The fixed-geometry model: no torsion domain to give.
  await app.locator("#model-kind").selectOption("fixed");
  await expect(app.getByLabel("φ domain (°) from")).toHaveCount(0);
  await expect(app.locator("#model-order")).toHaveValue("point-group");
  await expect(app.locator("#model-frame")).toHaveValue("symmetry");
  await app.getByRole("button", { name: "Apply" }).click();
  await expect(app.locator(".crumb .muted")).toContainText("rev 3 ");

  // 4. Import the couplings, confirming the mapping label by label.
  await app.locator("label.button", { hasText: "Choose a CSV file…" }).locator("input[type=file]").setInputFiles(CSV);
  const mapping = await confirmedMapping(server);
  for (const [label, spin] of Object.entries(mapping)) await app.locator(`[id="map-${label}"]`).selectOption(spin);
  await app.getByRole("button", { name: "Import 3 couplings" }).click();
  await expect(app.locator(".crumb .muted")).toContainText("rev 4 ");
  await expect(app.getByRole("note").filter({ hasText: "Ready to fit" })).toBeVisible();

  // 5. The fit: no torsion, no preview, no interval option.
  await openTab(app, "Fit");
  await expect(app.locator("#phi-slider")).toHaveCount(0);
  await expect(app.getByLabel("Profile intervals (slower)")).toHaveCount(0);
  await app.getByRole("button", { name: "Run fit" }).click();
  const estimable = pane(app, "pane-estimable");
  await expect(estimable.locator("tr[data-component]")).toHaveCount(2, { timeout: 120_000 });

  // 6. Select the worst row (largest |residual/σ|) in the run's residual table: its column "z".
  const table = pane(app, "pane-residuals").locator("table");
  await expect(table.locator("tbody tr")).toHaveCount(3);
  const worst = await table.evaluate((t) => {
    const head = [...t.querySelectorAll("thead th")].map((h) => h.textContent ?? "");
    const at = head.findIndex((h) => h.startsWith("Residual /"));
    if (at < 0) throw new Error(`no residual/σ column in ${head.join(" | ")}`);
    const rows = [...t.querySelectorAll("tbody tr")];
    const z = (r: Element) => Math.abs(Number((r.querySelectorAll("td")[at]?.textContent ?? "").replace("−", "-")));
    return rows.reduce((a, r) => (z(r) > z(a) ? r : a)).querySelector("td")?.textContent ?? "";
  });
  await table.locator("tbody tr", { hasText: worst }).first().click();
  await expect.poll(async () => (await server.ok("user", "render.describe_view")).selection.map((s: { label: string }) => s.label)).toEqual([worst]);
  const worstId = (await server.ok("user", "render.describe_view")).selection[0].id as string;
  // The Structure view draws the row's whole orbit selected: two arcs.
  await openTab(app, "Structure");
  await expect(app.locator(`path.arc.is-selected[data-id="${worstId}"]`)).toHaveCount(2);
  await openTab(app, "Data");
  const download = app.waitForEvent("download");
  await app.getByRole("button", { name: "Export" }).click();
  const exported = readFileSync((await (await download).path()) as string, "utf-8");

  // The robot, on its own server.
  const robotServer = await startServer();
  try {
    const robot = robotReport(robotServer);
    const page = await server.ok("user", "project.describe");
    expect(page.science_hash).toBe(robot.science_hash);
    expect(JSON.parse(exported)).toEqual(JSON.parse(robot.exported.text));
    const view = await server.ok("user", "render.describe_view");
    expect(view.selection.map((s: { id: string }) => s.id)).toEqual([robot.worst_coupling.id]);
    // The whole run, every field, each read with its own side's credential (round 54).
    const run = await server.ok("user", "run.get", { run_id: view.run.run_id });
    const robotView = await robotServer.ok("robot", "render.describe_view");
    const robotRun = await robotServer.ok("robot", "run.get", { run_id: robotView.run.run_id });
    expect(fixedResultDifferences(run.result, robotRun.result, TOLERANCES)).toEqual([]);
    // Round 79, finding 4: and the page shows the robot's numbers.
    await openTab(app, "Fit");
    await expectComponentsShown(pane(app, "pane-estimable"), robotRun.result.components);
    await expectVerdictShown(pane(app, "pane-run-detail"), robotRun.result); // round 80, finding 6
    const label = new Map((robotRun.result.spins as { id: string; label: string }[]).map((s) => [s.id, s.label]));
    const pairOf = new Map((robotRun.result.rows as { coupling_id: string; pair: [string, string] }[]).map((r) => [r.coupling_id, r.pair]));
    await expectRowsShown(pane(app, "pane-residuals").locator("table"), robotRun.result.rows, (id) =>
      (pairOf.get(id) ?? []).map((s) => label.get(s)).join("–"),
    );
    for (const key of ["kind", "input_hash", "science_hash", "science_revision", "stale"]) {
      expect(run.run[key], `run.${key}`).toEqual(robotRun.run[key]);
    }
    // The answer is the dataset's: both components estimated with supported intervals, adequacy given.
    const result = run.result as { components: { name: string; status: string; estimate: number; intervals: unknown[] | null }[]; adequacy: { status: string } };
    const estimated = result.components.filter((c) => c.status === "estimated");
    expect(estimated.map((c) => c.name)).toEqual(["Szz", "Sxx-Syy"]);
    for (const c of estimated) expect(c.intervals).toHaveLength(2);
    expect(result.adequacy.status).toBe("given");
    const truth = JSON.parse(readFileSync(join(DATA, "truth.json"), "utf-8")) as { truth: { Sxx: number; Syy: number } };
    expect(Math.abs((estimated[0]?.estimate ?? 0) + truth.truth.Sxx + truth.truth.Syy)).toBeLessThan(0.001);
  } finally {
    await robotServer.stop();
  }
});
