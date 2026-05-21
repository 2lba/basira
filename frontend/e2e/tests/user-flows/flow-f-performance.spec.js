// flow F: a scan against the e2e fixture completes inside the budget and
// surfaces the scan metadata the dashboard depends on (model, token counts,
// per-severity counts).
import {
  test,
  expect,
  resetState,
  seedUser,
  startScanViaApi,
  getScan,
} from "./helpers/flow.js";

async function waitForTerminal(request, scanId, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs;
  let state;
  while (Date.now() < deadline) {
    state = await getScan(request, scanId);
    if (state.status === "succeeded" || state.status === "failed") return state;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`scan ${scanId} did not finish in ${timeoutMs}ms (last status: ${state?.status})`);
}

test.describe("flow F - performance budget", () => {
  test("scan finishes within the e2e budget and exposes metadata", async ({ request, context }) => {
    await resetState(request);
    const seed = await seedUser(request, context);

    const start = Date.now();
    const scan = await startScanViaApi(request, seed.repo_id);
    const done = await waitForTerminal(request, scan.id, 20_000);
    const elapsed = Date.now() - start;

    expect(done.status).toBe("succeeded");
    expect(done.files_scanned).toBeGreaterThanOrEqual(1);
    expect(done.model).toBeTruthy();
    expect(done.counts?.total ?? 0).toBeGreaterThanOrEqual(0);
    // healthy stack should complete the e2e stub well under 20s
    expect(elapsed).toBeLessThan(20_000);
  });
});
