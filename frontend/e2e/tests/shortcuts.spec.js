// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("keyboard shortcuts", () => {
  test("? opens the help modal", async ({ page, seeded: _seeded }) => {
    await page.goto("/");
    // open via sidebar button (most reliable); also covered by ? key in real browsers
    await page.getByTestId("open-shortcuts").click();
    await expect(page.getByTestId("shortcuts-modal")).toBeVisible();
    await expect(page.getByTestId("shortcut-row")).toHaveCount(8);
  });

  test("g r navigates to repos and g s to settings", async ({
    page,
    seeded: _seeded,
  }) => {
    await page.goto("/about");
    await expect(page.getByTestId("about-page")).toBeVisible();
    await page.locator("body").click();

    await page.keyboard.press("g");
    await page.keyboard.press("r");
    await expect(page).toHaveURL(/\/$/);

    await page.keyboard.press("g");
    await page.keyboard.press("s");
    await expect(page).toHaveURL(/\/settings$/);

    await page.keyboard.press("g");
    await page.keyboard.press("h");
    await expect(page).toHaveURL(/\/scans$/);
  });

  test("n triggers scan now on a repo page", async ({ page, seeded }) => {
    await page.goto(`/repos/${seeded.repo_id}`);
    await expect(page.getByTestId("repo-detail")).toBeVisible();
    await page.locator("body").click();
    await page.keyboard.press("n");
    await expect(page.locator('[data-testid="active-scan-card"], [data-testid="scan-history"] a').first()).toBeVisible({ timeout: 25_000 });
  });

  test("/ focuses the findings search input on a scan page", async ({
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
    await page.locator("body").click();

    await page.keyboard.press("/");
    const input = page.getByTestId("findings-search");
    await expect(input).toBeFocused();
  });
});
