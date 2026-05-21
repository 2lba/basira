// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("unified settings", () => {
  test("/settings renders 3 tabs with account first", async ({
    page,
    seeded: _seeded,
  }) => {
    await page.goto("/settings");
    await expect(page.getByTestId("settings-page")).toBeVisible();
    await expect(page.getByTestId("tab-account")).toBeVisible();
    await expect(page.getByTestId("tab-notifications")).toBeVisible();
    await expect(page.getByTestId("tab-api-keys")).toBeVisible();
    await expect(page.getByTestId("account-tab")).toBeVisible();
    await expect(page.locator("body")).toContainText("playwright-user");
  });

  test("switching tabs updates the URL and content", async ({
    page,
    seeded: _seeded,
  }) => {
    await page.goto("/settings");
    await page.getByTestId("tab-notifications").click();
    await expect(page).toHaveURL(/\/settings\/notifications$/);
    await expect(page.getByTestId("notifications-tab")).toBeVisible();
    await expect(page.getByTestId("smtp-card")).toBeVisible();

    await page.getByTestId("tab-api-keys").click();
    await expect(page).toHaveURL(/\/settings\/api-keys$/);
    await expect(page.getByTestId("api-keys-tab")).toBeVisible();
    await expect(page.locator("body")).toContainText(/anthropic/i);

    await page.getByTestId("tab-account").click();
    await expect(page).toHaveURL(/\/settings$/);
    await expect(page.getByTestId("account-tab")).toBeVisible();
  });
});
