// The live preview's ordering hazards (rounds 47 and 48): project.describe and the view are read
// separately, so the domain can arrive after the revision that changed it.
import type { Page } from "@playwright/test";
import { expect, openExample, type Server, test } from "./harness";

const domain = (hi: number) => ({
  kind: "rigid",
  order: "bisector-diagonal",
  frame: "bisector",
  phi_domain: [
    { value: 0, unit: "deg" },
    { value: hi, unit: "deg" },
  ],
});

/** Holds every project.describe reply for `ms`, so the view's new revision arrives first. */
async function slowDescribe(page: Page, ms: number): Promise<void> {
  await page.route("**/api/v1/ops/project.describe", async (route) => {
    const response = await route.fetch();
    await new Promise((done) => setTimeout(done, ms));
    await route.fulfill({ response });
  });
}

async function setDomain(server: Server, hi: number): Promise<void> {
  await server.ok("robot", "model.set", { ...domain(hi), expected_science_revision: await server.revision() });
}

test("a narrowed domain clamps the preview, even when the domain arrives last (round 47)", async ({ app, server }) => {
  await openExample(server);
  await setDomain(server, 180);
  await app.getByRole("tab", { name: "Fit" }).click();
  await expect(app.locator("#phi-slider")).toHaveAttribute("max", "180");
  const field = app.getByLabel("φ in degrees");
  await field.fill("120");
  await field.press("Enter");
  await expect(app.locator(".meta")).toContainText("φ = 120.00°");
  await slowDescribe(app, 1500);
  await setDomain(server, 90);
  await expect(app.locator("#phi-slider")).toHaveAttribute("max", "90");
  await expect(app.locator("#phi-slider")).toHaveValue("90");
  await expect(field).toHaveValue("90.0");
  await expect(app.locator(".meta")).toContainText("φ = 90.00°");
});

/** The example's couplings again, with ring B's labels mirrored (H2′↔H6′, H3′↔H5′): on the
 * fixed-label domain [0°, 180°] the optimum moves from 37° to 143°, beyond the default 90°. */
async function mirrorRingB(server: Server): Promise<void> {
  const project = await server.ok("robot", "project.describe");
  const label = new Map<string, string>(project.spins.map((s: { id: string; label: string }) => [s.id, s.label]));
  const swap: Record<string, string> = { "H2'": "H6'", "H6'": "H2'", "H3'": "H5'", "H5'": "H3'" };
  const name = (id: string) => {
    const l = label.get(id) ?? id;
    return swap[l] ?? l;
  };
  const rows = project.couplings.map(
    (c: { spin_a: string; spin_b: string; value: { value: number }; sigma: { value: number } }) =>
      `${name(c.spin_a)},${name(c.spin_b)},${c.value.value},${c.sigma.value}`,
  );
  const csv = `spin_a,spin_b,D_obs_Hz,sigma_Hz\n${rows.join("\n")}\n`;
  const { proposed_mapping } = await server.ok("robot", "couplings.reconcile", { csv });
  await server.ok("robot", "couplings.import", {
    csv,
    confirmed_mapping: proposed_mapping,
    expected_science_revision: await server.revision(),
  });
}

test("the preview starts at the fit's φ even when the domain arrives last (round 48)", async ({ page, server }) => {
  await openExample(server);
  await mirrorRingB(server);
  await setDomain(server, 180);
  const run = await server.ok("robot", "fit.run", { expected_science_revision: await server.revision() });
  await server.ok("robot", "job.wait", { job_id: run.job.id });
  await slowDescribe(page, 1500);
  await page.goto(await server.launchUrl());
  await page.getByRole("tab", { name: "Fit" }).click();
  const fitted = page.getByRole("button", { name: /Go to the fit/ });
  await expect(fitted).toBeVisible();
  const phi = Number((/\(([0-9.]+)°\)/.exec((await fitted.textContent()) ?? "") ?? [])[1]);
  expect(phi).toBeGreaterThan(90); // beyond the default domain: a start clamped to it would be lost
  await expect(page.getByLabel("φ in degrees")).toHaveValue(phi.toFixed(1));
});

test("a typed negative angle (typographic minus) is understood (round 47)", async ({ app, server }) => {
  await openExample(server);
  await app.getByRole("tab", { name: "Fit" }).click();
  const field = app.getByLabel("φ in degrees");
  await expect(field).not.toHaveValue("");
  await field.fill("−5"); // U+2212; clamped to the domain's lower end
  await field.press("Enter");
  await expect(field).toHaveValue("0.0");
  await expect(app.locator(".meta")).toContainText("φ = 0.00°");
});
