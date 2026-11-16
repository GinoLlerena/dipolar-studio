// Large projects (M3 step 4b): tables above WINDOW_FROM rows render only the rows in view, and
// the Structure view draws at most MAX_DRAWN arcs, keeping the selection. A project of 72 protons
// with every pair coupled (2 556 couplings) is above both limits; the generator is the one in
// tools/bench/large_project.py (two groups of protons on spirals, synthetic values).

import type { Locator } from "@playwright/test";
import { expect, openTab, type Server, test } from "./harness";

const PROTONS = 72;
const COUPLINGS = (PROTONS * (PROTONS - 1)) / 2;

function largeProject(n: number): { xyz: string; csv: string } {
  const atoms: string[] = ["C 0 0 -0.75", "C 1.4 0 -1.5", "C 0 0 0.75", "C 1.4 0 1.5"];
  for (let k = 0; k < n; k++) {
    const side = k % 2 === 0 ? -1 : 1;
    const t = Math.floor(k / 2);
    const r = 2.5 + 0.35 * Math.sqrt(t);
    const a = 2.4 * t;
    atoms.push(`H ${(r * Math.cos(a)).toFixed(6)} ${(r * Math.sin(a)).toFixed(6)} ${(side * (2.5 + 0.03 * t)).toFixed(6)}`);
  }
  const xyz = `${atoms.length}\nlarge synthetic\n${atoms.join("\n")}\n`;
  const rows = ["spin_a,spin_b,D_obs_Hz,sigma_Hz"];
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) rows.push(`H${i + 5},H${j + 5},${(((i * 31 + j * 17) % 100) - 50).toFixed(1)},1`);
  }
  return { xyz, csv: `${rows.join("\n")}\n` };
}

/** Imports the large project over HTTP (the robot), with the mapping the server proposes. */
async function importLarge(server: Server): Promise<{ id: string; label: string }[]> {
  const { xyz, csv } = largeProject(PROTONS);
  let revision = (await server.ok("robot", "project.import_xyz", { xyz, name: "large", expected_science_revision: 0 }))
    .science_revision as number;
  const proposed = await server.ok("robot", "couplings.reconcile", { csv });
  expect(proposed.complete).toBe(true);
  revision = (
    await server.ok("robot", "couplings.import", {
      csv,
      confirmed_mapping: proposed.proposed_mapping,
      expected_science_revision: proposed.science_revision ?? revision,
    })
  ).science_revision as number;
  const couplings = (await server.ok("robot", "project.describe")).couplings as { id: string; label: string }[];
  expect(couplings).toHaveLength(COUPLINGS);
  return couplings;
}

function bodyRows(table: Locator): Locator {
  return table.locator("tbody tr:not(.spacer)");
}

test("a large couplings table renders only the rows in view", async ({ app, server }) => {
  const couplings = await importLarge(server);
  await openTab(app, "Data");
  const box = app.locator("#pane-couplings").locator("xpath=ancestor::section").locator(".scroll.windowed");
  await expect(box).toBeVisible();
  const rows = bodyRows(box.locator("table"));
  await expect(rows.first()).toContainText(couplings[0]!.label);
  const shown = await rows.count();
  expect(shown).toBeGreaterThan(5);
  expect(shown).toBeLessThan(200); // not 2 556
  // The scroll height still spans every row, so scrolling reaches the last coupling.
  await box.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await expect(rows.last()).toContainText(couplings[COUPLINGS - 1]!.label);
  expect(await rows.count()).toBeLessThan(200);
  // A selection made by another client is shown on the row once scrolled to it.
  await server.ok("robot", "view.select", { ids: [couplings[COUPLINGS - 1]!.id] });
  await expect(rows.last()).toHaveAttribute("aria-selected", "true");
});

test("a table replaced by a shorter one, still windowed, shows its last rows (round 51)", async ({ app, server }) => {
  const couplings = await importLarge(server);
  await openTab(app, "Data");
  const box = app.locator("#pane-couplings").locator("xpath=ancestor::section").locator(".scroll.windowed");
  const rows = bodyRows(box.locator("table"));
  await box.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await expect(rows.last()).toContainText(couplings[COUPLINGS - 1]!.label);
  // Another client loads the same project with only its first 500 couplings.
  const exported = JSON.parse((await server.ok("robot", "project.export")).text as string);
  exported.project.couplings = exported.project.couplings.slice(0, 500);
  const revision = await server.revision();
  await server.ok("robot", "project.load", { text: JSON.stringify(exported), expected_science_revision: revision });
  await expect(app.getByText("500 couplings").first()).toBeVisible();
  // The rows shown are the last ones, and stay shown (no oscillation between windows).
  await expect(rows.last()).toContainText(couplings[499]!.label);
  for (let i = 0; i < 5; i++) {
    await app.waitForTimeout(100);
    await expect(rows.last()).toContainText(couplings[499]!.label, { timeout: 100 });
    expect(await rows.count()).toBeGreaterThan(10);
  }
  await box.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await expect(rows.last()).toContainText(couplings[499]!.label);
});

test("the Structure view draws a bounded subset of the arcs and keeps the selection", async ({ app, server }) => {
  const couplings = await importLarge(server);
  const last = couplings[COUPLINGS - 1]!;
  await openTab(app, "Structure");
  const arcs = app.locator("path.arc[data-id]");
  await expect(arcs.first()).toBeAttached();
  const drawn = await arcs.count();
  expect(drawn).toBeGreaterThan(0);
  expect(drawn).toBeLessThanOrEqual(2000);
  await expect(app.getByText(`of ${COUPLINGS.toLocaleString("en")} couplings: the largest misfits`)).toBeVisible();
  // With no fit every misfit is unknown and the first 2 000 are drawn; the last coupling is drawn
  // once selected.
  await expect(app.locator(`path.arc[data-id="${last.id}"]`)).toHaveCount(0);
  await server.ok("robot", "view.select", { ids: [last.id] });
  await expect(app.locator(`path.arc.is-selected[data-id="${last.id}"]`)).toHaveCount(1);
  expect(await arcs.count()).toBeLessThanOrEqual(2000);
});
