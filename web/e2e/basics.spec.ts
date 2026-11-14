// The launch, the Data and Fit workspaces and staleness by content, through the page.
import { expect, openExample, test } from "./harness";

test("a launch link signs the tab in once; the session survives a reload", async ({ page, server }) => {
  const url = await server.launchUrl();
  await page.goto(url);
  await expect(page.locator(".conn-live")).toBeVisible();
  await expect(page).toHaveURL(`${server.base}/`); // the code left the address bar
  await page.reload();
  await expect(page.locator(".conn-live")).toBeVisible(); // the tab token, not the code
  // The same link again, in a new tab: single use, refused.
  const other = await page.context().newPage();
  await other.goto(url);
  await expect(other.getByText("This page needs a launch link")).toBeVisible();
  await expect(other.getByRole("alert")).toContainText("UNAUTHENTICATED");
});

test("open the example, fit it, and read the run", async ({ app }) => {
  await app.getByRole("button", { name: "Open the synthetic biphenyl example" }).click();
  await expect(app.locator(".crumb-name")).toHaveText("Synthetic biphenyl (known answer)");
  await app.getByRole("tab", { name: "Fit" }).click();
  await app.getByRole("button", { name: "Run fit" }).click();
  const status = app.locator(".statusbar");
  await expect(status).toContainText("Converged");
  await expect(status).toContainText("Identifiable");
  await expect(status).toContainText("χ²");
});

test("a run is stale after another client's change and current again after its undo", async ({ app, server }) => {
  await openExample(server);
  const revision = await server.revision();
  await server.ok("robot", "fit.run", { expected_science_revision: revision });
  const status = app.locator(".statusbar");
  await expect(status).toContainText("Converged");
  await server.ok("robot", "model.set", {
    kind: "jump4",
    order: "bisector-diagonal",
    frame: "bisector",
    phi_domain: [
      { value: 0, unit: "deg" },
      { value: 90, unit: "deg" },
    ],
    expected_science_revision: revision,
  });
  await expect(status).toContainText("Stale");
  await server.ok("robot", "history.undo", { expected_science_revision: revision + 1 });
  await expect(status).toContainText("Converged"); // the same content as the run's input
  await expect(status).not.toContainText("Stale");
});

