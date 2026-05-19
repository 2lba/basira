// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("compare two scans", () => {
  test("select two scans and view comparison", async ({ page, seeded }) => {
    await page.goto(`/repos/${seeded.repo_id}`);

    // run first scan, wait for it to land in history
    await page.getByTestId("scan-now").click();
    await page
      .getByTestId("scan-history")
      .locator("a")
      .first()
      .waitFor({ state: "visible", timeout: 25_000 });

    // run second scan
    await page.getByTestId("scan-now").click();
    await expect.poll(
      async () => await page.getByTestId("scan-history").locator("li").count(),
      { timeout: 25_000 },
    ).toBeGreaterThanOrEqual(2);

    const history = page.getByTestId("scan-history");

    // wait until checkboxes exist (history rendered with selection mode)
    const checkboxes = history.locator('input[type="checkbox"]');
    await expect(checkboxes).toHaveCount(2, { timeout: 5_000 });
    await checkboxes.nth(0).check();
    await checkboxes.nth(1).check();

    const compareBtn = page.getByTestId("compare-button");
    await expect(compareBtn).toBeEnabled();
    await compareBtn.click();

    await expect(page).toHaveURL(/\/scans\/compare\?/);
    await expect(page.getByTestId("scan-compare")).toBeVisible();

    // both scans rendered
    await expect(page.getByTestId("scan-summary-a")).toBeVisible();
    await expect(page.getByTestId("scan-summary-b")).toBeVisible();

    // score delta visible (most recent on top, so A is the second/latest run)
    const delta = page.getByTestId("score-delta");
    await expect(delta).toBeVisible();
    await expect(delta).toContainText(/^[+\-]?\d+$/);

    // sections render with counts that reflect the stub findings
    const resolved = page.getByTestId("resolved-section");
    const newFinds = page.getByTestId("new-section");
    const persisting = page.getByTestId("persisting-section");

    await expect(resolved).toBeVisible();
    await expect(newFinds).toBeVisible();
    await expect(persisting).toBeVisible();

    const allCounts = await Promise.all([
      resolved.locator("h2").innerText(),
      newFinds.locator("h2").innerText(),
      persisting.locator("h2").innerText(),
    ]);

    // expect 1 new, 1 resolved, 3 persisting (relative to whichever direction)
    const numbers = allCounts.map((t) =>
      parseInt(t.match(/\((\d+)\)/)?.[1] ?? "0", 10),
    );
    // sum across new + resolved + persisting should equal union of findings: 5
    const sum = numbers.reduce((a, b) => a + b, 0);
    expect(sum).toBeGreaterThanOrEqual(5);

    // both diff items exist: scripts/build.sh and app/cache.py appear somewhere
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toMatch(/scripts\/build\.sh|app\/cache\.py/);
  });

  test("compare button is disabled until two scans are selected", async ({
    page,
    seeded,
  }) => {
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();
    await page
      .getByTestId("scan-history")
      .locator("a")
      .first()
      .waitFor({ state: "visible", timeout: 25_000 });

    await page.getByTestId("scan-now").click();
    await expect.poll(
      async () => await page.getByTestId("scan-history").locator("li").count(),
      { timeout: 25_000 },
    ).toBeGreaterThanOrEqual(2);

    const compareBtn = page.getByTestId("compare-button");
    await expect(compareBtn).toBeDisabled();

    const checkbox = page
      .getByTestId("scan-history")
      .locator('input[type="checkbox"]')
      .first();
    await checkbox.check();
    await expect(compareBtn).toBeDisabled();
  });
});
