// @ts-check
import { test, expect } from "./fixtures.js";

const API_BASE = process.env.E2E_API_BASE || "http://localhost:8001";

test.describe("empty states + skeletons", () => {
  test("scans index empty state offers a way back to repos", async ({
    page,
    seeded: _seeded,
  }) => {
    // seeded gives us an authed user with one repo and zero scans
    await page.goto("/scans");
    await expect(page.getByTestId("scans-empty")).toBeVisible();
    await expect(page.getByTestId("empty-state-title")).toContainText(/no scans/i);
    await page.getByRole("link", { name: /choose a repository/i }).click();
    await expect(page).toHaveURL(/\/$/);
  });

  test("skeleton renders while repos call is in flight", async ({
    page,
    seeded: _seeded,
  }) => {
    await page.route("**/api/repos", async (route) => {
      await new Promise((r) => setTimeout(r, 800));
      return route.continue();
    });
    await page.goto("/");
    await expect(page.getByTestId("repos-skeleton")).toBeVisible();
    // and then real content
    await expect(page.locator('a[href*="/repos/"]').first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test("scan detail shows a skeleton while loading", async ({
    page,
    seeded,
  }) => {
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();
    const firstRow = page.getByTestId("scan-history").locator("a").first();
    await firstRow.waitFor({ state: "visible", timeout: 25_000 });
    const href = await firstRow.getAttribute("href");

    await page.route(`**${href.replace(/^.*\/scans\//, "/api/scans/")}`, async (route) => {
      await new Promise((r) => setTimeout(r, 700));
      return route.continue();
    });

    await page.goto(href);
    await expect(page.getByTestId("scan-skeleton")).toBeVisible();
  });
});
