// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("scan repository flow", () => {
  test("happy path: open repo, scan now, see progress and report", async ({
    page,
    seeded,
  }) => {
    await page.goto(`/repos/${seeded.repo_id}`);
    await expect(page.getByTestId("repo-detail")).toBeVisible();
    await expect(page.getByText(seeded.repo_full_name)).toBeVisible();

    const scanBtn = page.getByTestId("scan-now");
    await expect(scanBtn).toBeEnabled();

    await scanBtn.click();

    const activeCard = page.getByTestId("active-scan-card");
    await expect(activeCard).toBeVisible({ timeout: 10_000 });

    const progressBar = page.getByTestId("active-progress-bar");
    await expect(progressBar).toBeVisible();

    // wait until progress advances past 10%
    await expect.poll(
      async () => {
        const w = await progressBar.evaluate((el) => el.style.width);
        const n = parseInt(w, 10);
        return Number.isFinite(n) ? n : 0;
      },
      { timeout: 15_000 },
    ).toBeGreaterThan(10);

    // eventually the scan finishes and shows up in history
    const historyList = page.getByTestId("scan-history");
    await expect(historyList).toBeVisible({ timeout: 20_000 });
    await expect(historyList.locator("a").first()).toBeVisible();
  });

  test("score and findings render on scan detail page", async ({
    page,
    seeded,
  }) => {
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();

    // open the most-recent scan once it lands in history
    const firstRow = page.getByTestId("scan-history").locator("a").first();
    await firstRow.waitFor({ state: "visible", timeout: 25_000 });
    await firstRow.click();

    const detail = page.getByTestId("scan-detail");
    await expect(detail).toBeVisible();

    // summary mentions findings counts
    await expect(page.getByTestId("scan-summary")).toContainText("Found");

    // severity chips show 4 categories
    const chips = page.getByTestId("severity-chips");
    await expect(chips).toBeVisible();
    await expect(page.getByTestId("chip-critical")).toContainText("1");
    await expect(page.getByTestId("chip-major")).toContainText("1");

    // each severity group renders
    await expect(page.getByTestId("severity-group-critical")).toBeVisible();
    await expect(page.getByTestId("severity-group-major")).toBeVisible();

    // findings list renders with at least 4 items
    const findings = page.getByTestId("finding-item");
    await expect(findings).toHaveCount(4);
  });

  test("opening a finding shows details and github link", async ({
    page,
    seeded,
  }) => {
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();

    const firstRow = page.getByTestId("scan-history").locator("a").first();
    await firstRow.waitFor({ state: "visible", timeout: 25_000 });
    await firstRow.click();

    const firstFinding = page.getByTestId("finding-item").first();
    await expect(firstFinding).toBeVisible();
    await expect(firstFinding.getByTestId("finding-message")).toContainText(
      /timing attack/i,
    );

    // click to expand
    await firstFinding.locator("button").first().click();

    const details = firstFinding.getByTestId("finding-details");
    await expect(details).toBeVisible();
    const link = details.getByTestId("github-link");
    await expect(link).toBeVisible();
    const href = await link.getAttribute("href");
    expect(href).toContain("github.com/playwright-user/sample-repo/blob/");
    expect(href).toMatch(/#L\d+$/);
  });

  test("scan history shows previous scans across visits", async ({
    page,
    request: _request,
    seeded,
  }) => {
    // run two scans by triggering, waiting, then triggering again
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();
    await page
      .getByTestId("scan-history")
      .locator("a")
      .first()
      .waitFor({ state: "visible", timeout: 25_000 });

    await page.getByTestId("scan-now").click();
    await expect.poll(
      async () => (await page.getByTestId("scan-history").locator("a").count()),
      { timeout: 25_000 },
    ).toBeGreaterThanOrEqual(2);

    // navigating away and back keeps history
    await page.goto("/");
    await page.goto(`/repos/${seeded.repo_id}`);
    await expect(page.getByTestId("scan-history").locator("a")).toHaveCount(2, {
      timeout: 10_000,
    });
  });

  test("scans index lists scans across repos", async ({ page, seeded }) => {
    // create one scan
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();
    await page
      .getByTestId("scan-history")
      .locator("a")
      .first()
      .waitFor({ state: "visible", timeout: 25_000 });

    await page.goto("/scans");
    await expect(page.getByText(seeded.repo_full_name)).toBeVisible();
  });
});
