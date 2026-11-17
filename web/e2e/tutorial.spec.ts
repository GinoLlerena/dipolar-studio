// The biphenyl tutorial (04 §7 "Robot user"): the same steps through the page and by the robot
// (tools/robot/robot.py --scenario tutorial: HTTP registry calls only, in a clean `python -I`
// process with no frontend, browser or dipolar packages), each on its own server. "The final
// project and results equal those of the UI path": the science hash, the exported project, the
// whole run (every field, with the frozen quantity-specific tolerances: e2e/compare.ts), the run's
// inputs and the selected coupling are compared.

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { resultDifferences, type Tolerances } from "./compare";
import { expect, openTab, type Server, startServer, test } from "./harness";

const ROOT = resolve(import.meta.dirname, "../..");
const DATA = join(ROOT, "datasets", "biphenyl-synthetic");
const XYZ = join(DATA, "biphenyl.xyz");
const CSV = join(DATA, "tutorial-couplings.csv");
const TORSION = ["1", "0", "6", "7"]; // C2–C1–C1'–C2'
const PYTHON = process.env.DIPOLAR_ROBOT_PYTHON ?? "python3";
/** The frozen regression tolerances (04 §8.6: quantity-specific). */
const TOLERANCES = (JSON.parse(readFileSync(join(DATA, "expected", "spec.json"), "utf-8")) as { tolerances: { regression: Tolerances } })
  .tolerances.regression;

type Named = { name: string; value: number };
type Fit = {
  theta: Named[];
  order: Named[];
  chi2: number;
  nu: number | null;
  stderr: Named[] | null;
  intervals: { parameter: string; estimate: number; lower: number | null; upper: number | null; supported: boolean }[];
};

/** The robot's tutorial on its own server: its JSON report. */
function robotTutorial(server: Server): Record<string, any> {
  try {
    return robotReport(server);
  } catch (error) {
    // The robot prints its failure as a JSON line on stdout: show it (a failure under load in M3
    // beta step B2 showed only the command line).
    const e = error as { stdout?: string; stderr?: string; message: string };
    throw new Error(`the robot failed: ${e.stdout?.trim() || e.message}\n${e.stderr?.trim() ?? ""}`);
  }
}

function robotReport(server: Server): Record<string, any> {
  const report = execFileSync(
    PYTHON,
    [
      "-I",
      join(ROOT, "tools", "robot", "robot.py"),
      "--ready-file",
      join(server.dir, "ready.json"),
      "--scenario",
      "tutorial",
      "--xyz",
      XYZ,
      "--csv",
      CSV,
      "--phi",
      "-37",
    ],
    { encoding: "utf-8", timeout: 600_000 },
  );
  const parsed = JSON.parse(report) as Record<string, any>;
  if (!parsed.ok) throw new Error(`the robot failed: ${parsed.error}`);
  return parsed;
}

/** The mapping a user confirms: the file's labels to the imported protons, by the atom names in
 * the XYZ comment line and each spin's atom index (as the robot does). */
async function confirmedMapping(server: Server): Promise<Record<string, string>> {
  const names = (readFileSync(XYZ, "utf-8").split("\n")[1] ?? "").split("atoms:")[1]?.trim().split(/\s+/) ?? [];
  const spins = (await server.ok("user", "project.describe")).spins as { id: string; atom: number }[];
  const labels = ["H2", "H3", "H4", "H5", "H6", "H2'", "H3'", "H4'", "H5'", "H6'"];
  return Object.fromEntries(labels.map((l) => [l, spins.find((s) => s.atom === names.indexOf(l))?.id ?? ""]));
}

test("the tutorial through the page equals the robot's", async ({ app, server }) => {
  test.setTimeout(240_000);
  // 1. Create the project from the user's geometry.
  await openTab(app, "Data");
  await app.locator("label.button", { hasText: "Import XYZ geometry…" }).locator("input[type=file]").setInputFiles(XYZ);
  await expect(app.locator(".crumb-name")).toHaveText("biphenyl");

  // 2. Import the couplings, confirming the mapping label by label.
  await app.locator("label.button", { hasText: "Choose a CSV file…" }).locator("input[type=file]").setInputFiles(CSV);
  const mapping = await confirmedMapping(server);
  for (const [label, spin] of Object.entries(mapping)) {
    await app.locator(`[id="map-${label}"]`).selectOption(spin);
  }
  await app.getByRole("button", { name: "Import 14 couplings" }).click();
  await expect(app.locator(".crumb .muted")).toContainText("rev 2 ");

  // 3. Bind the torsion; the model for imported geometry.
  for (const [k, value] of TORSION.entries()) await app.getByLabel(["a", "i", "j", "b"][k] as string, { exact: true }).fill(value);
  await expect(app.getByRole("button", { name: "Set torsion" })).toBeEnabled();
  await app.getByRole("button", { name: "Set torsion" }).click();
  await expect(app.locator(".crumb .muted")).toContainText("rev 3 ");
  await app.locator("#model-kind").selectOption("rigid");
  await app.locator("#model-order").selectOption("c2z");
  await app.locator("#model-frame").selectOption("input");
  await app.getByLabel("φ domain (°) from").fill("-90");
  await app.getByLabel("φ domain (°) to").fill("0");
  await app.getByRole("button", { name: "Apply" }).click();
  await expect(app.locator(".crumb .muted")).toContainText("rev 4 ");
  await expect(app.getByRole("note").filter({ hasText: "Ready to fit" })).toBeVisible();

  // 4. Preview at φ; the profile fit.
  await openTab(app, "Fit");
  const field = app.getByLabel("φ in degrees");
  await expect(field).not.toHaveValue(""); // started
  await field.fill("-37");
  await field.press("Enter");
  await expect(app.locator(".meta")).toContainText("φ = −37.00°");
  await app.getByLabel("Profile intervals (slower)").check();
  await app.getByRole("button", { name: "Run fit" }).click();
  await expect(app.locator(".statusbar")).toContainText("Converged", { timeout: 120_000 });

  // 5. Select the worst coupling (largest |residual/σ|) in the run's residual table.
  const table = app.locator("#pane-residuals").locator("xpath=ancestor::section").locator("table");
  await expect(table.locator("tbody tr")).toHaveCount(14);
  const worst = await table.evaluate((t) => {
    const rows = [...t.querySelectorAll("tbody tr")];
    const z = (r: Element) => Math.abs(Number((r.querySelectorAll("td")[5]?.textContent ?? "").replace("−", "-")));
    const best = rows.reduce((a, r) => (z(r) > z(a) ? r : a));
    return best.querySelector("td")?.textContent ?? "";
  });
  await table.locator("tbody tr", { hasText: worst }).first().click();
  await expect(table.locator("tbody tr.selected")).toHaveCount(1);
  // The shared view selects that coupling, and the Structure view draws exactly its arc selected
  // (round 53: one selected arc, whichever, passed).
  await expect.poll(async () => (await server.ok("user", "render.describe_view")).selection.map((s: { label: string }) => s.label)).toEqual([worst]);
  const worstId = (await server.ok("user", "render.describe_view")).selection[0].id as string;
  await openTab(app, "Structure"); // the rendered view, with the selection
  await expect(app.locator("path.arc.is-selected")).toHaveCount(1);
  await expect(app.locator(`path.arc.is-selected[data-id="${worstId}"]`)).toHaveCount(1);
  await openTab(app, "Data");
  const download = app.waitForEvent("download");
  await app.getByRole("button", { name: "Export" }).click();
  const exported = readFileSync((await (await download).path()) as string, "utf-8");

  // The robot, on its own server.
  const robotServer = await startServer();
  try {
    const robot = robotTutorial(robotServer);
    const page = await server.ok("user", "project.describe");
    expect(page.science_hash).toBe(robot.science_hash);
    expect(JSON.parse(exported)).toEqual(JSON.parse(robot.exported.text));
    const view = await server.ok("user", "render.describe_view");
    expect(view.selection.map((s: { label: string }) => s.label)).toEqual([robot.worst_coupling.label]);
    expect(view.selection.map((s: { id: string }) => s.id)).toEqual([robot.worst_coupling.id]);
    // The whole run, every field (round 53): the page's and the robot's, each read with run.get.
    const run = await server.ok("user", "run.get", { run_id: view.run.run_id });
    // Read with the robot's own credential (round 54: read as the user, a server that answered
    // the user differently corrupted both sides alike and the comparison passed).
    const robotView = await robotServer.ok("robot", "render.describe_view");
    const robotRun = await robotServer.ok("robot", "run.get", { run_id: robotView.run.run_id });
    expect(resultDifferences(run.result, robotRun.result, TOLERANCES)).toEqual([]);
    for (const key of ["kind", "input_hash", "science_hash", "science_revision", "stale"]) {
      expect(run.run[key], `run.${key}`).toEqual(robotRun.run[key]);
    }
    const ours = run.result as Fit;
    // The intervals exist and are usable (round 52: two empty lists compared equal): every
    // parameter of the model, each supported with finite bounds around its estimate.
    expect(ours.intervals.map((i) => i.parameter)).toEqual(["phi_deg", "Szz", "Delta", "Sxy"]);
    for (const iv of ours.intervals) {
      expect(iv.supported, `${iv.parameter} supported`).toBe(true);
      expect(Number.isFinite(iv.lower) && Number.isFinite(iv.upper), `${iv.parameter} bounds`).toBe(true);
      expect((iv.lower as number) <= iv.estimate && iv.estimate <= (iv.upper as number), `${iv.parameter} estimate`).toBe(true);
    }
    // And the answer is the dataset's: τ = −φ, φ = 37°, within the torsion's interval.
    const tau = ours.theta[0]?.value ?? Number.NaN;
    expect(Math.abs(tau + 37)).toBeLessThan(0.1);
    const torsion = ours.intervals[0]!;
    expect((torsion.lower as number) < -37 && -37 < (torsion.upper as number), "−37° within the interval").toBe(true);
  } finally {
    await robotServer.stop();
  }
});

test("a science change while the torsion is typed keeps what was typed (CI, M3 step 4b)", async ({ app, server }) => {
  // On CI's Firefox the couplings import's new project description arrived after the torsion was
  // typed, and the fields were reset to the (undeclared) torsion: Set torsion stayed disabled.
  const xyz = readFileSync(XYZ, "utf-8");
  await server.ok("robot", "project.import_xyz", { xyz, name: "biphenyl", expected_science_revision: 0 });
  await openTab(app, "Data");
  await expect(app.locator(".crumb .muted")).toContainText("rev 1 ");
  for (const [k, value] of TORSION.entries()) await app.getByLabel(["a", "i", "j", "b"][k] as string, { exact: true }).fill(value);
  // Another client imports the couplings (a science change) while the fields hold the typing.
  const csv = readFileSync(CSV, "utf-8");
  const mapping = await confirmedMapping(server);
  await server.ok("robot", "couplings.import", { csv, confirmed_mapping: mapping, expected_science_revision: 1 });
  await expect(app.getByText("14 couplings").first()).toBeVisible(); // the new description is shown
  for (const [k, value] of TORSION.entries()) {
    await expect(app.getByLabel(["a", "i", "j", "b"][k] as string, { exact: true })).toHaveValue(value);
  }
  await expect(app.getByRole("button", { name: "Set torsion" })).toBeEnabled();
  await app.getByRole("button", { name: "Set torsion" }).click();
  await expect(app.locator(".crumb .muted")).toContainText("rev 3 ");
  await expect(app.locator("fieldset.torsion .muted")).toHaveText(TORSION.join(" – "));
});

test("typed torsion indices are reset when another geometry replaces the first (round 52)", async ({ app, server }) => {
  // The same molecule with C2 and C6 swapped: indices 1 0 6 7 now name another dihedral (+143°).
  const xyz = readFileSync(XYZ, "utf-8");
  await server.ok("robot", "project.import_xyz", { xyz, name: "first", expected_science_revision: 0 });
  await openTab(app, "Data");
  await expect(app.locator(".crumb-name")).toHaveText("first");
  for (const [k, value] of TORSION.entries()) await app.getByLabel(["a", "i", "j", "b"][k] as string, { exact: true }).fill(value);
  const lines = xyz.trimEnd().split("\n");
  const atoms = lines.slice(2);
  [atoms[1], atoms[5]] = [atoms[5]!, atoms[1]!];
  const [head, list] = (lines[1] ?? "").split("atoms:");
  const names = (list ?? "").trim().split(/\s+/);
  [names[1], names[5]] = [names[5]!, names[1]!];
  const swapped = [lines[0], `${head}atoms: ${names.join(" ")}`, ...atoms].join("\n") + "\n";
  await server.ok("robot", "project.import_xyz", { xyz: swapped, name: "second", expected_science_revision: 1 });
  await expect(app.locator(".crumb-name")).toHaveText("second");
  for (const k of [0, 1, 2, 3]) await expect(app.getByLabel(["a", "i", "j", "b"][k] as string, { exact: true })).toHaveValue("");
  await expect(app.getByRole("button", { name: "Set torsion" })).toBeDisabled();
});
