// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("public share link", () => {
  test("create link then open it in a clean context with no auth", async ({
    page,
    browser,
    seeded,
  }) => {
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();

    const firstRow = page.getByTestId("scan-history").locator("a").first();
    await firstRow.waitFor({ state: "visible", timeout: 25_000 });
    await firstRow.click();

    await expect(page.getByTestId("scan-detail")).toBeVisible();

    await page.getByTestId("share-button").click();
    const modal = page.getByTestId("share-modal");
    await expect(modal).toBeVisible();

    const urlInput = modal.getByTestId("share-url-input");
    await expect(urlInput).toBeVisible({ timeout: 5_000 });
    const url = await urlInput.inputValue();
    expect(url).toMatch(/\/shared\/[A-Za-z0-9_-]{20,}/);

    // open in a fresh context: no auth cookies, public access
    const clean = await browser.newContext();
    const cleanPage = await clean.newPage();
    await cleanPage.goto(url);
    await expect(cleanPage.getByTestId("shared-scan")).toBeVisible();
    await expect(cleanPage.locator("body")).toContainText(
      "playwright-user/sample-repo",
    );
    await expect(cleanPage.locator("body")).toContainText(/timing attack/i);
    await clean.close();
  });

  test("revoking the link makes it return not-found publicly", async ({
    page,
    browser,
    seeded,
  }) => {
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();

    const firstRow = page.getByTestId("scan-history").locator("a").first();
    await firstRow.waitFor({ state: "visible", timeout: 25_000 });
    await firstRow.click();

    await page.getByTestId("share-button").click();
    const modal = page.getByTestId("share-modal");
    const urlInput = modal.getByTestId("share-url-input");
    await expect(urlInput).toBeVisible({ timeout: 5_000 });
    const url = await urlInput.inputValue();

    // revoke
    await modal.getByTestId("share-revoke-button").click();
    await expect(modal).not.toBeVisible();

    const clean = await browser.newContext();
    const cleanPage = await clean.newPage();
    await cleanPage.goto(url);
    await expect(cleanPage.getByTestId("shared-not-found")).toBeVisible({
      timeout: 5_000,
    });
    await clean.close();
  });
});
