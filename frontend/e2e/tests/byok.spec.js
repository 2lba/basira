// @ts-check
import { test, expect, seedWithoutApiKey } from "./fixtures.js";

test.describe("byok flow", () => {
  test("banner shows when no key, vanishes after the user adds one", async ({
    page,
    request,
    context,
  }) => {
    await seedWithoutApiKey(request, context);

    await page.goto("/");
    const banner = page.getByTestId("missing-key-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText(/anthropic api key/i);

    await banner.getByTestId("missing-key-banner-cta").click();
    await expect(page).toHaveURL(/\/settings\/api-keys$/);
    await expect(page.getByTestId("anthropic-key-empty")).toBeVisible();

    await page.getByTestId("add-key-btn").click();
    await page
      .getByTestId("api-key-input")
      .fill("sk-ant-e2e-playwright-add-key-1234567890");
    await page.getByTestId("save-key-btn").click();

    await expect(page.getByTestId("anthropic-key-configured")).toBeVisible();
    await expect(page.getByTestId("key-status-valid")).toBeVisible();
    // banner should refresh and disappear once the key is saved
    await expect(banner).toBeHidden();

    // sanity-check the API: the plain key never appears in any response body
    const listResp = await request.get(
      `${process.env.E2E_API_BASE || "http://localhost:8001"}/api/me/api-keys`,
      { headers: { cookie: (await context.cookies()).map((c) => `${c.name}=${c.value}`).join("; ") } },
    );
    expect(listResp.ok()).toBeTruthy();
    const listText = await listResp.text();
    expect(listText).not.toContain("sk-ant-e2e-playwright-add-key");
  });

  test("scan started without a key fails with the missing-key cta", async ({
    page,
    request,
    context,
  }) => {
    const seed = await seedWithoutApiKey(request, context);

    await page.goto(`/repos/${seed.repo_id}`);
    await expect(page.getByTestId("repo-detail")).toBeVisible();
    await page.getByTestId("scan-now").click();

    // the e2e scan engine fails immediately when the user has no key
    const cta = page.getByTestId("repo-add-api-key");
    await expect(page.getByTestId("repo-missing-key")).toBeVisible({
      timeout: 15_000,
    });
    await expect(cta).toBeVisible();
    await cta.click();
    await expect(page).toHaveURL(/\/settings\/api-keys$/);
  });

  test("missing-key banner can be dismissed and stays dismissed", async ({
    page,
    request,
    context,
  }) => {
    await seedWithoutApiKey(request, context);

    await page.goto("/");
    const banner = page.getByTestId("missing-key-banner");
    await expect(banner).toBeVisible();

    await page.getByTestId("missing-key-banner-dismiss").click();
    await expect(banner).toBeHidden();

    // reload — banner stays hidden because localStorage flag persists
    await page.reload();
    await expect(page.getByTestId("missing-key-banner")).toBeHidden();
  });
});
