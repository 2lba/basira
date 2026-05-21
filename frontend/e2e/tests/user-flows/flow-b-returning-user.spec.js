// flow B: returning user reruns a scan, both runs land in history.
import {
  test,
  expect,
  resetState,
  seedUser,
  startScanViaApi,
  getScan,
  listScansForRepo,
} from "./helpers/flow.js";

async function waitForTerminal(request, scanId, timeoutMs = 25_000) {
  const deadline = Date.now() + timeoutMs;
  let state;
  while (Date.now() < deadline) {
    state = await getScan(request, scanId);
    if (state.status === "succeeded" || state.status === "failed") return state;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`scan ${scanId} did not finish in ${timeoutMs}ms`);
}

test.describe("flow B - returning user", () => {
  test("rescan then compare against the previous run", async ({ page, request, context }) => {
    await resetState(request);
    const seed = await seedUser(request, context);

    // first scan via api, wait for the worker to terminal-state it
    const first = await startScanViaApi(request, seed.repo_id);
    const firstDone = await waitForTerminal(request, first.id);
    expect(firstDone.status).toBe("succeeded");

    // second scan via the UI
    await page.goto(`/repos/${seed.repo_id}`);
    await expect(page.getByTestId("repo-detail")).toBeVisible();
    await page.getByTestId("scan-now").click();

    const rows = page.getByTestId("scan-history").locator("a");
    await expect(rows).toHaveCount(2, { timeout: 25_000 });
    const scans = await listScansForRepo(request, seed.repo_id);
    await waitForTerminal(request, scans[0].id);

    await page.reload();
    await expect(rows).toHaveCount(2);
  });
});
