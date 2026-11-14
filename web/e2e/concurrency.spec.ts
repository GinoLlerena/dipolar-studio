// 04 §7 "Concurrency": a UI edit and a robot edit at the same revision; one applies, the other is
// refused with REVISION_CONFLICT, and nothing is lost.
import { expect, openExample, test } from "./harness";

test("the page's edit made at an older revision is refused; the robot's stays", async ({ app, server }) => {
  await openExample(server);
  await app.getByRole("tab", { name: "Data" }).click();
  await expect(app.locator("#model-kind")).toBeVisible();
  // The robot's edit lands while the page's request is on its way, at the same revision.
  await app.route("**/api/v1/ops/model.set", async (route) => {
    const revision = await server.revision();
    await server.ok("robot", "model.set", {
      kind: "rigid",
      order: "bisector-diagonal",
      frame: "bisector",
      phi_domain: [
        { value: 0, unit: "deg" },
        { value: 180, unit: "deg" },
      ],
      expected_science_revision: revision,
    });
    await route.continue();
  });
  await app.locator("#model-kind").selectOption("jump4");
  await app.getByRole("button", { name: "Apply" }).click();
  await expect(app.locator(".error[role=alert]")).toContainText("REVISION_CONFLICT");
  const project = await server.ok("robot", "project.describe");
  expect(project.model.kind).toBe("rigid"); // the robot's edit is kept, not overwritten
  expect(project.model.phi_domain[1].value).toBe(180);
  await expect(app.locator(".crumb .muted")).toContainText("rev 2"); // the page follows it
});
