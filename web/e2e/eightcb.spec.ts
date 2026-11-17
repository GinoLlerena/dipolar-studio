// The testers' exercise (docs/beta/testers.md, beta step B4), in the app, click for click: the 8CB
// couplings at T_red = 0.930 with σ = 1 ("unweighted") on the biphenyl template, the four-site
// jump, a fit; the result equals the reference values the guide gives. The couplings come from the
// repository's validation copy of Di Pietro (2013), Table 3.1, as a tester would transcribe them;
// the test is skipped when that third-party dataset is absent (it is removable on request).
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { expect, openTab, test } from "./harness";

const SOURCE = resolve(import.meta.dirname, "../../datasets/biphenyl-8CB-dipietro2013/couplings.csv");
const GUIDE = { phi_deg: 32.932, Szz: 0.43075, Delta: 0.18524 }; // docs/beta/testers.md
const PRINTED = { phi_deg: 1e-3, Szz: 1e-5, Delta: 1e-5 }; // the guide's printed digits

test.skip(!existsSync(SOURCE), "the third-party 8CB dataset is not present");

test("the testers' 8CB exercise in the app gives the guide's values", async ({ app, server }) => {
  test.setTimeout(180_000);
  const rows = readFileSync(SOURCE, "utf-8")
    .trim()
    .split("\n")
    .slice(1)
    .map((line) => line.match(/("[^"]*"|[^,]+)/g) ?? [])
    .filter((cells) => cells[0] === "0.930");
  expect(rows).toHaveLength(12);
  const file = join(tmpdir(), `8cb-unweighted-${process.pid}.csv`);
  writeFileSync(file, `spin_a,spin_b,D_obs_Hz,sigma_Hz\n${rows.map((c) => `${c[2]},${c[3]},${c[4]},1`).join("\n")}\n`);

  await openTab(app, "Data");
  await app.getByRole("button", { name: "Open the synthetic biphenyl example" }).click();
  await expect(app.locator(".crumb .muted")).toContainText("rev 1 ");
  await app.locator("label.button", { hasText: "Choose a CSV file…" }).locator("input[type=file]").setInputFiles(file);
  await app.getByRole("button", { name: "Import 12 couplings" }).click();
  await expect(app.locator(".crumb .muted")).toContainText("rev 2 ");
  await app.locator("#model-kind").selectOption("jump4");
  await app.locator("#model-order").selectOption("bisector-diagonal");
  await app.locator("#model-frame").selectOption("bisector");
  await app.getByLabel("φ domain (°) from").fill("0");
  await app.getByLabel("φ domain (°) to").fill("90");
  await app.getByRole("button", { name: "Apply" }).click();
  await expect(app.locator(".crumb .muted")).toContainText("rev 3 ");
  await openTab(app, "Fit");
  await app.getByRole("button", { name: "Run fit" }).click();
  await expect(app.locator(".statusbar")).toContainText("Converged", { timeout: 120_000 });

  const view = await server.ok("robot", "render.describe_view");
  const run = (await server.ok("robot", "run.get", { run_id: view.run.run_id })).result;
  const values: Record<string, number> = {};
  for (const v of [...run.theta, ...run.order]) values[v.name] = v.value;
  for (const [key, expected] of Object.entries(GUIDE) as [keyof typeof GUIDE, number][]) {
    expect(Math.abs((values[key] ?? Number.NaN) - expected), key).toBeLessThanOrEqual(PRINTED[key]);
  }
  expect(run.model.kind).toBe("jump4");
  expect(run.n_obs).toBe(12);
});
