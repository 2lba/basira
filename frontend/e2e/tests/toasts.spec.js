// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("error toasts", () => {
  test("api error shows a toast with retry button", async ({
    page,
    seeded: _seeded,
  }) => {
    // intercept /api/scans and return 500 for the first request, success for retry
    let count = 0;
    await page.route("**/api/scans", (route) => {
      count += 1;
      if (count === 1) {
        return route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({
            error: { code: "BOOM", message: "internal server error" },
          }),
        });
      }
      return route.continue();
    });

    await page.goto("/scans");
    const toast = page.getByTestId("toast");
    await expect(toast).toBeVisible({ timeout: 5_000 });
    await expect(toast.getByTestId("toast-message")).toContainText(/internal server error/i);
    const retry = toast.getByTestId("toast-retry");
    await expect(retry).toBeVisible();
    await retry.click();

    // retry should clear the toast and the page should hydrate (empty list ok)
    await expect(page.getByTestId("toast-stack")).toHaveCount(0);
  });

  test("dismiss removes the toast", async ({ page, seeded: _seeded }) => {
    await page.route("**/api/scans", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error: { code: "DOWN", message: "service unavailable" },
        }),
      }),
    );
    await page.goto("/scans");
    const toast = page.getByTestId("toast");
    await expect(toast).toBeVisible({ timeout: 5_000 });
    await toast.getByTestId("toast-dismiss").click();
    await expect(page.getByTestId("toast-stack")).toHaveCount(0);
  });
});
