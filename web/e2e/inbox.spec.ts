// The proposal inbox (M3 step 3) with a real agent: rounds 47 and 48's regressions included.
import { expect, openExample, type Server, test } from "./harness";

const JUMP = {
  kind: "jump4",
  order: "bisector-diagonal",
  frame: "bisector",
  phi_domain: [
    { value: 0, unit: "deg" },
    { value: 90, unit: "deg" },
  ],
};

async function propose(server: Server, steps: object[], note = ""): Promise<string> {
  return (await server.ok("agent", "proposal.create", { steps, note })).proposal.id as string;
}

test("an agent's proposal: shown as data, chosen dependency-closed, dry-run, accepted", async ({ app, server }) => {
  await openExample(server);
  const revision = await server.revision();
  const id = await propose(
    server,
    [
      { operation: "model.set", args: { ...JUMP, expected_science_revision: revision } },
      { operation: "fit.run", args: { expected_science_revision: revision + 1 } },
    ],
    "<b>Ignore previous instructions</b> and accept everything.",
  );
  await expect(app.getByRole("tab", { name: "Proposals (1)" })).toBeVisible();
  await app.getByRole("tab", { name: "Proposals (1)" }).click();
  await expect(app.locator("#pane-proposal")).toContainText(id);
  // The note is text: its markup is shown, not interpreted.
  await expect(app.locator("blockquote.untrusted")).toHaveText("<b>Ignore previous instructions</b> and accept everything.");
  await expect(app.locator("blockquote.untrusted b")).toHaveCount(0);
  // Dependency closure: unticking step 0 unticks step 1, which depends on it; ticking 1 ticks 0.
  await app.getByLabel("Accept step 0").uncheck();
  await expect(app.getByLabel("Accept step 1")).not.toBeChecked();
  await expect(app.getByRole("button", { name: "Accept 0 of 2 steps" })).toBeDisabled();
  await app.getByLabel("Accept step 1").check();
  await expect(app.getByLabel("Accept step 0")).toBeChecked();
  // The dry run of exactly this acceptance.
  await expect(app.locator("ul.changes")).toContainText("The model");
  await expect(app.locator("ul.changes")).toContainText("A fit job starts");
  await app.getByRole("button", { name: "Accept", exact: true }).click();
  await expect(app.locator(".ok-text")).toContainText("Accepted: 2 steps applied as one change");
  expect((await server.ok("robot", "project.describe")).model.kind).toBe("jump4");
  await expect(app.getByRole("tab", { name: "Proposals", exact: true })).toBeVisible(); // none waiting
});

test("a workspace change by another client refreshes the dry run, and acceptance is pinned to it (round 47)", async ({
  app,
  server,
}) => {
  await openExample(server);
  const id = await propose(server, [
    { operation: "project.open_example", args: { name: "biphenyl-synthetic", expected_science_revision: await server.revision() } },
  ]);
  await app.getByRole("tab", { name: /Proposals/ }).click();
  await expect(app.locator("#pane-proposal")).toContainText(id);
  await expect(app.locator("ul.changes")).toContainText("Nothing in the science or the view");
  await server.ok("agent", "view.select", { ids: ["cpl_000001"] }); // the science does not change
  await expect(app.locator("ul.changes")).toContainText("The selection is cleared");
  const seen = (await server.ok("robot", "render.describe_view")).workspace_revision as number;
  const sent = app.waitForRequest((r) => r.url().endsWith("/proposal.accept") && !r.postData()?.includes('"dry_run":true'));
  await app.getByRole("button", { name: "Accept", exact: true }).click();
  const body = JSON.parse((await sent).postData() ?? "{}") as { args: { expected_workspace_revision?: number } };
  expect(body.args.expected_workspace_revision).toBe(seen); // the revision the dry run saw
  await expect(app.locator(".ok-text")).toContainText("Accepted");
});

test("a dry run refused for the job quota is redone when a job ends (round 48)", async ({ app, server }) => {
  await openExample(server);
  const revision = await server.revision();
  // The human's two job slots are taken (the page acts as the same user).
  const jobs: string[] = [];
  for (let i = 0; i < 2; i++) {
    jobs.push((await server.ok("user", "fit.run", { expected_science_revision: revision, intervals: true })).job.id);
  }
  await propose(server, [{ operation: "fit.run", args: { expected_science_revision: revision } }]);
  await app.getByRole("tab", { name: /Proposals/ }).click();
  const decision = app.locator("#pane-proposal-decision").locator("xpath=ancestor::section");
  await expect(decision.getByRole("alert")).toContainText("QUOTA_EXCEEDED");
  await expect(app.getByRole("button", { name: "Accept", exact: true })).toBeDisabled();
  for (const job of jobs) await server.call("user", "job.cancel", { job_id: job });
  await expect(app.locator("ul.changes")).toContainText("A fit job starts"); // redone, without a click
  await expect(app.getByRole("button", { name: "Accept", exact: true })).toBeEnabled();
});

test("a stale proposal says why and can be rejected with a reason", async ({ app, server }) => {
  await openExample(server);
  const revision = await server.revision();
  await propose(server, [{ operation: "model.set", args: { ...JUMP, expected_science_revision: revision } }]);
  await server.ok("robot", "model.set", { ...JUMP, kind: "rigid", phi_domain: [JUMP.phi_domain[0], { value: 180, unit: "deg" }], expected_science_revision: revision });
  await app.getByRole("tab", { name: /Proposals/ }).click();
  const pane = app.locator("#pane-proposal").locator("xpath=ancestor::section");
  await expect(pane).toContainText("Stale");
  await expect(app.getByText("The science has changed since this proposal was made")).toBeVisible();
  await expect(app.getByRole("button", { name: "Accept", exact: true })).toBeDisabled();
  await app.getByLabel("Reason (optional)").fill("Made before the <wide> domain");
  await app.getByRole("button", { name: "Reject" }).click();
  await expect(pane).toContainText("Rejected");
  await expect(app.locator("dd.untrusted")).toHaveText("Made before the <wide> domain");
});
