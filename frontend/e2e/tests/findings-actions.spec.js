// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("finding actions", () => {
  test("mark resolved hides the finding", async ({ page, seeded }) => {
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();
    await page
      .getByTestId("scan-history")
      .locator("a")
      .first()
      .waitFor({ state: "visible", timeout: 25_000 });
    await page.getByTestId("scan-history").locator("a").first().click();

    const items = page.getByTestId("finding-item");
    await expect(items).toHaveCount(4);

    await items.first().locator("button").first().click();
    await items.first().getByTestId("action-resolve").click();

    await expect(items).toHaveCount(3, { timeout: 5_000 });
    await expect(page.getByTestId("hidden-count")).toContainText("1");
  });

  test("false positive persists across future scans", async ({
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
    await page.getByTestId("scan-history").locator("a").first().click();

    // expand first finding and mark false positive
    const first = page.getByTestId("finding-item").first();
    await first.locator("button").first().click();
    await first.getByTestId("action-false-positive").click();
    await expect(page.getByTestId("finding-item")).toHaveCount(3);

    // trigger a rescan and open the new scan
    await page.getByTestId("rescan-button").click();
    await expect(page.getByTestId("scan-detail")).toBeVisible();
    await expect.poll(
      async () => {
        const items = page.getByTestId("finding-item");
        return await items.count();
      },
      { timeout: 25_000 },
    ).toBeLessThanOrEqual(3);

    // the critical "timing attack" finding must be gone
    await expect(page.locator("body")).not.toContainText(/timing attack/i);
  });

  test("ignore rule hides all findings of that category in this view", async ({
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
    await page.getByTestId("scan-history").locator("a").first().click();

    const items = page.getByTestId("finding-item");
    await expect(items).toHaveCount(4);

    // critical finding has category "security"; ignore it
    await items.first().locator("button").first().click();
    await items.first().getByTestId("action-ignore-rule").click();

    await expect(items).toHaveCount(3, { timeout: 5_000 });
    await expect(page.locator("body")).not.toContainText(/timing attack/i);
  });
});
