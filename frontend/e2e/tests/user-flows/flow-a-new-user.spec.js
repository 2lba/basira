// flow A: brand-new user adds key, runs a scan, resolves a finding.
import {
  test,
  expect,
  resetState,
  seedUser,
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

test.describe("flow A - new user journey", () => {
  test("first login, add key, scan, resolve finding", async ({ page, request, context }) => {
    await resetState(request);
    const seed = await seedUser(request, context, { withKey: false });

    // banner visible on the landing
    await page.goto("/");
    await expect(page.getByTestId("missing-key-banner")).toBeVisible();

    await page.getByTestId("missing-key-banner-cta").click();
    await expect(page).toHaveURL(/\/settings\/api-keys$/);

    // add a valid e2e-prefixed key
    await page.getByTestId("add-key-btn").click();
    await page.getByTestId("api-key-input").fill("sk-ant-e2e-flow-a-newuser-key-1234");
    await page.getByTestId("save-key-btn").click();
    await expect(page.getByTestId("anthropic-key-configured")).toBeVisible();
    await expect(page.getByTestId("key-status-valid")).toBeVisible();
    await expect(page.getByTestId("missing-key-banner")).toBeHidden();

    // start a scan from the repo page
    await page.goto(`/repos/${seed.repo_id}`);
    await expect(page.getByTestId("repo-detail")).toBeVisible();
    await page.getByTestId("scan-now").click();

    // wait for the worker to finish via the api so we do not race the
    // finalize-now route against the worker writes.
    const firstRow = page.getByTestId("scan-history").locator("a").first();
    await firstRow.waitFor({ state: "visible", timeout: 25_000 });
    const scans = await listScansForRepo(request, seed.repo_id);
    const latest = scans[0];
    await waitForTerminal(request, latest.id);

    await page.goto(`/scans/${latest.id}`);
    await expect(page.getByTestId("scan-detail")).toBeVisible();
    await expect(page.getByTestId("severity-chips")).toBeVisible();
    const items = page.getByTestId("finding-item");
    await expect(items).toHaveCount(4);

    // expand the first finding, then resolve it. the actions are only
    // rendered once the row is expanded.
    const firstFinding = items.first();
    await firstFinding.locator("button").first().click();
    await firstFinding.getByTestId("action-resolve").click();
    await expect(items).toHaveCount(3, { timeout: 5_000 });
  });
});
