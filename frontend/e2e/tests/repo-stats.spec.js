// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("repo stats chart", () => {
  test("chart appears after two completed scans", async ({ page, seeded }) => {
    await page.goto(`/repos/${seeded.repo_id}`);

    // no chart with zero scans
    await expect(page.getByTestId("score-chart")).toHaveCount(0);

    // run two scans
    await page.getByTestId("scan-now").click();
    await page
      .getByTestId("scan-history")
      .locator("a")
      .first()
      .waitFor({ state: "visible", timeout: 25_000 });

    // still no chart with only one scan
    await expect(page.getByTestId("score-chart")).toHaveCount(0);

    await page.getByTestId("scan-now").click();
    await expect.poll(
      async () => await page.getByTestId("scan-history").locator("li").count(),
      { timeout: 25_000 },
    ).toBeGreaterThanOrEqual(2);

    // chart now visible with svg inside
    const chart = page.getByTestId("score-chart");
    await expect(chart).toBeVisible();
    await expect(chart).toContainText("score trend");
    await expect(chart.locator("svg")).toHaveCount(1);
  });
});
