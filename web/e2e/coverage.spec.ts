// UI coverage (04 §7: "100% of UI domain actions are registry operations"), checked by effect:
// every control of the page that changes shared state is used here, and the change is read back
// by another client from the server. A control that changed only the page (round 53: a layer
// toggle made local hid couplings while the server still had them visible) fails here.
//
// The other commands' controls are covered the same way elsewhere: importing an XYZ file and a
// couplings file, confirming the mapping, setting the torsion and the model, fitting, selecting a
// residual row and exporting (tutorial.spec.ts: the science hash, the run and the export are read
// from the server); a proposal's acceptance and rejection (below, read back with proposal.get).

import { expect, openTab, test } from "./harness";

const OPEN = { name: "biphenyl-synthetic", expected_science_revision: 0 };

test("opening the example and undo/redo in the page change the server's project", async ({ app, server }) => {
  await openTab(app, "Data");
  await app.getByRole("button", { name: "Open the synthetic biphenyl example" }).click();
  await expect.poll(async () => (await server.ok("robot", "render.describe_view")).science_revision).toBe(1);
  expect((await server.ok("robot", "render.describe_view")).project_open).toBe(true);
  const opened = await server.ok("robot", "project.describe");
  // Another client changes the model; the page undoes it, then redoes it.
  const jump = { kind: "jump4", order: "bisector-diagonal", frame: "bisector", phi_domain: [{ value: 0, unit: "deg" }, { value: 90, unit: "deg" }] };
  await server.ok("robot", "model.set", { ...jump, expected_science_revision: await server.revision() });
  await expect(app.locator(".crumb .muted")).toContainText("rev 2 ");
  await app.getByRole("button", { name: /Undo/ }).click();
  await expect.poll(async () => (await server.ok("robot", "project.describe")).science_hash).toBe(opened.science_hash);
  await app.getByRole("button", { name: /Redo/ }).click();
  await expect.poll(async () => (await server.ok("robot", "project.describe")).model.kind).toBe("jump4");
});

test("loading a project file in the page loads it on the server", async ({ app, server }) => {
  await server.ok("robot", "project.open_example", OPEN);
  const exported = await server.ok("robot", "project.export");
  const text = JSON.parse(exported.text as string);
  text.project.name = "loaded from a file";
  await server.ok("robot", "model.set", {
    kind: "rigid",
    order: "bisector-diagonal",
    frame: "bisector",
    phi_domain: [{ value: 0, unit: "deg" }, { value: 180, unit: "deg" }],
    expected_science_revision: 1,
  });
  await openTab(app, "Data");
  await app.locator("label.button", { hasText: "Load a project file…" }).locator("input[type=file]").setInputFiles({
    name: "loaded.dipolar.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(text)),
  });
  await expect.poll(async () => (await server.ok("robot", "render.describe_view")).project_name).toBe("loaded from a file");
  expect((await server.ok("robot", "project.describe")).model.phi_domain[1].value).toBe(90); // the file's, not the edit's
});

test("the layer toggles change the shared view's layers", async ({ app, server }) => {
  await server.ok("robot", "project.open_example", OPEN);
  await openTab(app, "Structure");
  const layers = async () => (await server.ok("robot", "render.scene")).layers as Record<string, boolean>;
  expect(await layers()).toEqual({ labels: true, bonds: true, couplings: true });
  for (const [label, key] of [
    ["Labels", "labels"],
    ["Bonds", "bonds"],
    ["Couplings", "couplings"],
  ] as const) {
    const box = app.locator("#pane-layers").locator("xpath=ancestor::section").getByLabel(label, { exact: true });
    // A controlled checkbox: it changes when the server's view does (a click, then the read).
    await box.click();
    await expect.poll(async () => (await layers())[key]).toBe(false);
    await expect(box).not.toBeChecked();
    await box.click();
    await expect.poll(async () => (await layers())[key]).toBe(true);
    await expect(box).toBeChecked();
  }
});

test("rotating and fitting the camera in the page moves the shared camera", async ({ app, server }) => {
  await server.ok("robot", "project.open_example", OPEN);
  await openTab(app, "Structure");
  const camera = async () => JSON.stringify((await server.ok("robot", "render.scene")).camera);
  const before = await camera();
  const view = app.getByRole("group", { name: /atoms/ });
  // A gesture names the view revision its camera was moved from, and the server refuses one that
  // a newer camera replaced (rounds 41–42). So each gesture waits until the page has the server's
  // current view, as a user acts on what is shown (CI Firefox: a wheel right after "0" was refused).
  const settled = async () =>
    expect(view).toHaveAttribute(
      "data-workspace-revision",
      String((await server.ok("robot", "render.scene")).workspace_revision),
    );
  await view.focus();
  await view.press("ArrowRight");
  await view.press("ArrowRight");
  await expect.poll(camera, { timeout: 10_000 }).not.toBe(before);
  const rotated = await camera();
  await settled();
  await view.press("+"); // zoom
  await expect.poll(camera, { timeout: 10_000 }).not.toBe(rotated);
  const zoomed = await camera();
  await settled();
  // A drag with the pointer, from the middle of the view.
  const box = (await view.boundingBox())!;
  await app.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await app.mouse.down();
  await app.mouse.move(box.x + box.width / 2 + 60, box.y + box.height / 2 + 20, { steps: 6 });
  await app.mouse.up();
  await expect.poll(camera, { timeout: 10_000 }).not.toBe(zoomed);
  const dragged = await camera();
  await settled();
  await view.press("0"); // fit the molecule: the automatic camera again
  await expect.poll(camera, { timeout: 10_000 }).not.toBe(dragged);
  const fitted = await camera();
  await settled();
  // The wheel zooms (round 54: it was untested).
  await app.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await app.mouse.wheel(0, -240);
  await expect.poll(camera, { timeout: 10_000 }).not.toBe(fitted);
  await settled();
  // The "Fit to view" button: the automatic camera again.
  await app.getByRole("button", { name: "Fit to view" }).click();
  await expect.poll(camera, { timeout: 10_000 }).toBe(fitted);
});

test("selecting in the Structure view and clearing it change the shared selection", async ({ app, server }) => {
  await server.ok("robot", "project.open_example", OPEN);
  await openTab(app, "Structure");
  const selection = async () => (await server.ok("robot", "render.describe_view")).selection.map((s: { id: string }) => s.id);
  const first = (await server.ok("robot", "project.describe")).couplings[0] as { id: string; label: string };
  const table = app.locator("#pane-structure-couplings").locator("xpath=ancestor::section").locator("table");
  await table.locator("tbody tr", { hasText: first.label }).first().click();
  await expect.poll(selection).toEqual([first.id]);
  await app.locator("#pane-selection").locator("xpath=ancestor::section").getByRole("button", { name: "Clear" }).click();
  await expect.poll(selection).toEqual([]);
  // An arc, then an atom (a spin), clicked in the view.
  const second = (await server.ok("robot", "project.describe")).couplings[1] as { id: string };
  await app.locator(`path.arc[data-id="${second.id}"]`).dispatchEvent("click");
  await expect.poll(selection).toEqual([second.id]);
  const spin = (await server.ok("robot", "project.describe")).spins[0] as { id: string };
  await app.locator(`g[data-id="${spin.id}"] circle`).dispatchEvent("click");
  await expect.poll(selection).toEqual([spin.id]);
});

test("every other selecting control selects on the server (round 54)", async ({ app, server }) => {
  await server.ok("robot", "project.open_example", OPEN);
  const job = (await server.ok("robot", "fit.run", { expected_science_revision: 1 })).job.id as string;
  await expect.poll(async () => (await server.ok("robot", "job.status", { job_id: job })).job.status, { timeout: 30_000 }).toBe("succeeded");
  const project = await server.ok("robot", "project.describe");
  const c = project.couplings as { id: string; label: string }[];
  const spins = project.spins as { id: string; label: string }[];
  const selection = async () => (await server.ok("robot", "render.describe_view")).selection.map((s: { id: string }) => s.id);
  // The Data tab's couplings and spins tables, by click and by keyboard.
  await openTab(app, "Data");
  const section = (id: string) => app.locator(`#${id}`).locator("xpath=ancestor::section");
  await section("pane-couplings").locator("tbody tr:not(.spacer)", { hasText: c[0]!.label }).first().click();
  await expect.poll(selection).toEqual([c[0]!.id]);
  await section("pane-spins").locator("tbody tr", { hasText: spins[0]!.label }).first().click();
  await expect.poll(selection).toEqual([spins[0]!.id]);
  const row = section("pane-couplings").locator("tbody tr:not(.spacer)", { hasText: c[1]!.label }).first();
  await row.focus();
  await row.press("Enter");
  await expect.poll(selection).toEqual([c[1]!.id]);
  // Shift-click adds an arc to the selection.
  await openTab(app, "Structure");
  await app.locator(`path.arc[data-id="${c[2]!.id}"]`).dispatchEvent("click", { shiftKey: true });
  await expect.poll(selection).toEqual([c[1]!.id, c[2]!.id]);
  // A point of the run's observed-against-calculated plot.
  await openTab(app, "Fit");
  const point = app.locator("#pane-residuals").locator("xpath=ancestor::section").locator("circle.plot-point").filter({ hasText: c[3]!.label });
  await point.first().dispatchEvent("click");
  await expect.poll(selection).toEqual([c[3]!.id]);
});

test("cancelling a job in the page cancels it on the server", async ({ app, server }) => {
  await server.ok("robot", "project.open_example", OPEN);
  await openTab(app, "Fit");
  await app.getByLabel("Profile intervals (slower)").check();
  await app.getByRole("button", { name: "Run fit" }).click();
  const jobs = async () => (await server.ok("robot", "job.list")).jobs as { id: string; status: string }[];
  await expect.poll(async () => (await jobs()).length).toBe(1);
  await app.getByRole("button", { name: "Cancel" }).click();
  await expect.poll(async () => (await jobs())[0]?.status, { timeout: 30_000 }).toBe("cancelled");
});

test("accepting and rejecting proposals in the page decide them on the server", async ({ app, server }) => {
  await server.ok("robot", "project.open_example", OPEN);
  const propose = async (kind: string, hi: number) =>
    (
      await server.ok("agent", "proposal.create", {
        note: `${kind} on [0, ${hi}]`,
        steps: [
          {
            operation: "model.set",
            args: {
              kind,
              order: "bisector-diagonal",
              frame: "bisector",
              phi_domain: [{ value: 0, unit: "deg" }, { value: hi, unit: "deg" }],
              expected_science_revision: 1,
            },
          },
        ],
      })
    ).proposal.id as string;
  const accepted = await propose("rigid", 180);
  const rejected = await propose("jump4", 90);
  const status = async (id: string) => (await server.ok("robot", "proposal.get", { proposal_id: id })).proposal.status;
  await openTab(app, /Proposals/);
  const row = (id: string) => app.locator('table[aria-labelledby="pane-proposals"] tbody tr', { hasText: id });
  const pane = app.locator("#pane-proposal").locator("xpath=ancestor::section");
  await row(accepted).click();
  await expect(pane).toContainText(accepted);
  await expect(app.getByRole("button", { name: "Accept", exact: true })).toBeEnabled();
  await app.getByRole("button", { name: "Accept", exact: true }).click();
  await expect.poll(() => status(accepted)).toBe("accepted");
  expect((await server.ok("robot", "project.describe")).model.phi_domain[1].value).toBe(180);
  await row(rejected).click();
  await expect(pane).toContainText(rejected);
  await app.getByRole("button", { name: "Reject" }).click();
  await expect.poll(() => status(rejected)).toBe("rejected");
});
