// The biphenyl tutorial (04 §7 "Robot user"): the same steps through the page and by the robot
// (tools/robot/robot.py --scenario tutorial: HTTP registry calls only, in a clean `python -I`
// process with no frontend, browser or dipolar packages), each on its own server. "The final
// project and results equal those of the UI path": the science hash, the exported project, the
// fit and the selected coupling are compared.

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { expect, openTab, type Server, startServer, test } from "./harness";

const ROOT = resolve(import.meta.dirname, "../..");
const DATA = join(ROOT, "datasets", "biphenyl-synthetic");
const XYZ = join(DATA, "biphenyl.xyz");
const CSV = join(DATA, "tutorial-couplings.csv");
const TORSION = ["1", "0", "6", "7"]; // C2–C1–C1'–C2'
const PYTHON = process.env.DIPOLAR_ROBOT_PYTHON ?? "python3";

type Named = { name: string; value: number };
type Fit = {
  theta: Named[];
  order: Named[];
  chi2: number;
  nu: number | null;
  stderr: Named[] | null;
  intervals: { parameter: string; lower: number | null; upper: number | null; supported: boolean }[];
};

/** The robot's tutorial on its own server: its JSON report. */
function robotTutorial(server: Server): Record<string, any> {
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

function close(a: number | null, b: number | null, rtol = 1e-9, atol = 1e-12): boolean {
  if (a === null || b === null) return a === b;
  return Math.abs(a - b) <= atol + rtol * Math.max(Math.abs(a), Math.abs(b));
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
  await openTab(app, "Structure"); // the rendered view, with the selection
  await expect(app.locator("path.arc.is-selected")).toHaveCount(1);
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
    const run = await server.ok("user", "run.get", { run_id: view.run.run_id });
    const ours = run.result as Fit;
    const theirs = robot.fit as Fit;
    // Quantity-specific tolerances (04 §8.6): the same inputs on the same engine; the last bits may
    // differ between processes (D11).
    for (const key of ["theta", "order", "stderr"] as const) {
      const a = ours[key] ?? [];
      const b = theirs[key] ?? [];
      expect(a.map((v) => v.name)).toEqual(b.map((v) => v.name));
      a.forEach((v, i) => expect(close(v.value, b[i]?.value ?? Number.NaN), `${key} ${v.name}`).toBe(true));
    }
    expect(close(ours.chi2, theirs.chi2)).toBe(true);
    expect(ours.nu).toBe(theirs.nu);
    expect(ours.intervals.map((i) => [i.parameter, i.supported])).toEqual(theirs.intervals.map((i) => [i.parameter, i.supported]));
    ours.intervals.forEach((iv, k) => {
      expect(close(iv.lower, theirs.intervals[k]?.lower ?? null, 1e-9, 1e-9), `${iv.parameter} lower`).toBe(true);
      expect(close(iv.upper, theirs.intervals[k]?.upper ?? null, 1e-9, 1e-9), `${iv.parameter} upper`).toBe(true);
    });
    // And the answer is the dataset's: τ = −φ, φ = 37°, within the interval.
    const tau = ours.theta[0]?.value ?? Number.NaN;
    expect(Math.abs(tau + 37)).toBeLessThan(0.1);
  } finally {
    await robotServer.stop();
  }
});
