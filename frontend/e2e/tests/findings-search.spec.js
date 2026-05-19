// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("findings search", () => {
  test("typing filters findings in real time", async ({ page, seeded }) => {
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

    const input = page.getByTestId("findings-search");
    await expect(input).toBeVisible();

    await input.fill("timing");
    await expect(items).toHaveCount(1);
    await expect(items.first()).toContainText(/timing attack/i);

    await input.fill("N+1");
    await expect(items).toHaveCount(1);
    await expect(items.first()).toContainText(/N\+1/);

    // category filter
    await input.fill("performance");
    await expect(items).toHaveCount(1);

    // file path filter
    await input.fill("build.sh");
    await expect(items).toHaveCount(1);

    await input.fill("nothingthatmatches");
    await expect(items).toHaveCount(0);
    await expect(page.locator("body")).toContainText(/filtered out/i);

    await input.fill("");
    await expect(items).toHaveCount(4);
  });
});
