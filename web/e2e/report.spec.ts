// The run's summary report (beta step B2): the page's downloads are the server's run.report, byte
// for byte (the same run gives the same report).
import { readFileSync } from "node:fs";
import { expect, openExample, openTab, test } from "./harness";

test("the report downloads are the server's report of the run", async ({ app, server }) => {
  await openExample(server);
  const job = (await server.ok("robot", "fit.run", { expected_science_revision: 1 })).job.id as string;
  await expect
    .poll(async () => (await server.ok("robot", "job.status", { job_id: job })).job.status, { timeout: 60_000 })
    .toBe("succeeded");
  const runId = (await server.ok("robot", "render.describe_view")).run.run_id as string;
  const report = await server.ok("robot", "run.report", { run_id: runId });
  await openTab(app, "Fit");
  const pane = app.locator("#pane-run-detail").locator("xpath=ancestor::section");
  await expect(pane).toContainText(runId);
  for (const [button, name, text] of [
    ["Download report", `${report.filename}.html`, report.html],
    ["Couplings CSV", `${report.filename}.csv`, report.csv],
  ] as const) {
    const download = app.waitForEvent("download");
    await pane.getByRole("button", { name: button }).click();
    const file = await download;
    expect(file.suggestedFilename()).toBe(name);
    expect(readFileSync((await file.path()) as string, "utf-8")).toBe(text);
  }
});
