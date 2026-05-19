// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("onboarding tour", () => {
  test.beforeEach(async ({ page }) => {
    // ensure localStorage is fresh per test
    await page.addInitScript(() => {
      try {
        window.localStorage.removeItem("basira_tour_completed");
      } catch {}
    });
  });

  test("appears on first visit and walks through 3 steps", async ({
    page,
    seeded: _seeded,
  }) => {
    await page.goto("/");
    const tour = page.getByTestId("onboarding-tour");
    await expect(tour).toBeVisible();
    await expect(tour.getByTestId("tour-step")).toContainText("step 1 of 3");
    await expect(tour.getByTestId("tour-title")).toContainText("welcome");

    await tour.getByTestId("tour-next").click();
    await expect(tour.getByTestId("tour-step")).toContainText("step 2 of 3");

    await tour.getByTestId("tour-next").click();
    await expect(tour.getByTestId("tour-step")).toContainText("step 3 of 3");
    await expect(tour.getByTestId("tour-next")).toContainText(/got it/);

    await tour.getByTestId("tour-next").click();
    await expect(tour).not.toBeVisible();
  });

  test("skip dismisses the tour and persists", async ({
    page,
    seeded: _seeded,
  }) => {
    await page.goto("/");
    const tour = page.getByTestId("onboarding-tour");
    await tour.getByTestId("tour-skip").click();
    await expect(tour).not.toBeVisible();

    // localStorage should mark the tour done
    const flag = await page.evaluate(() =>
      window.localStorage.getItem("basira_tour_completed"),
    );
    expect(flag).toBe("1");

    await page.reload();
    await expect(page.getByTestId("onboarding-tour")).toHaveCount(0);
  });

  test("does not appear if flag is already set", async ({
    page,
    seeded: _seeded,
  }) => {
    await page.addInitScript(() => {
      try {
        window.localStorage.setItem("basira_tour_completed", "1");
      } catch {}
    });
    await page.goto("/");
    await expect(page.getByTestId("onboarding-tour")).toHaveCount(0);
  });
});
