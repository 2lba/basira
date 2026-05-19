// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("rescan and export", () => {
  test("rescan button on scan detail starts a new scan", async ({
    page,
    seeded,
  }) => {
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();

    const firstRow = page.getByTestId("scan-history").locator("a").first();
    await firstRow.waitFor({ state: "visible", timeout: 25_000 });
    await firstRow.click();

    await expect(page.getByTestId("scan-detail")).toBeVisible();
    const originalUrl = page.url();

    const rescan = page.getByTestId("rescan-button");
    await expect(rescan).toBeEnabled();
    await rescan.click();

    // we should land on a new scan page
    await expect.poll(() => page.url(), { timeout: 10_000 }).not.toBe(
      originalUrl,
    );
    await expect(page.getByTestId("scan-detail")).toBeVisible();

    // and after the new one finishes, repo history shows 2 scans
    await page.goto(`/repos/${seeded.repo_id}`);
    await expect.poll(
      async () => await page.getByTestId("scan-history").locator("a").count(),
      { timeout: 25_000 },
    ).toBeGreaterThanOrEqual(2);
  });

  test("export as markdown downloads a .md file with findings", async ({
    page,
    seeded,
  }) => {
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();
    const firstRow = page.getByTestId("scan-history").locator("a").first();
    await firstRow.waitFor({ state: "visible", timeout: 25_000 });
    await firstRow.click();

    await expect(page.getByTestId("scan-detail")).toBeVisible();

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("export-md-button").click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toMatch(/\.md$/);
    expect(download.suggestedFilename()).toContain("playwright-user");

    const path = await download.path();
    const fs = await import("node:fs");
    const text = fs.readFileSync(path, "utf-8");

    expect(text).toContain("# Scan report");
    expect(text).toContain("playwright-user/sample-repo");
    expect(text).toMatch(/Score: \*\*\d+ \/ 100\*\*/);
    expect(text).toContain("## Critical");
    expect(text).toContain("app/auth.py");
    expect(text).toContain("timing attack");
    expect(text).toContain("github.com/playwright-user/sample-repo/blob/");
  });
});
