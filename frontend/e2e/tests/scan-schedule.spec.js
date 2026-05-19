// @ts-check
import { test, expect } from "./fixtures.js";

const API_BASE = process.env.E2E_API_BASE || "http://localhost:8001";

test.describe("scan scheduling", () => {
  test("set a daily schedule that matches now and a tick triggers a scan", async ({
    page,
    request,
    seeded,
  }) => {
    // configure daily schedule on the repo to match current UTC time
    const now = new Date();
    const hour = now.getUTCHours();
    const minute = now.getUTCMinutes();

    await page.goto(`/repos/${seeded.repo_id}`);
    const card = page.getByTestId("schedule-card");
    await expect(card).toBeVisible();
    await card.getByTestId("schedule-kind").selectOption("daily");
    await card.getByTestId("schedule-hour").fill(String(hour));
    await card.getByTestId("schedule-minute").fill(String(minute));
    await page.getByRole("button", { name: /save changes/ }).click();
    // settle: wait for the button to flip back from "saving..."
    await page
      .getByRole("button", { name: /save changes/ })
      .waitFor({ state: "attached" });

    // ensure no in-flight scan from earlier setup
    await page.waitForTimeout(300);

    // tick the scheduler
    const tickRes = await request.post(`${API_BASE}/test/scheduler/tick`);
    expect(tickRes.ok()).toBe(true);
    const tickBody = await tickRes.json();
    expect(Array.isArray(tickBody.scan_ids)).toBe(true);
    expect(tickBody.scan_ids.length).toBeGreaterThanOrEqual(1);

    // scan eventually shows up in the repo history
    await page.reload();
    await expect.poll(
      async () => await page.getByTestId("scan-history").locator("a").count(),
      { timeout: 25_000 },
    ).toBeGreaterThanOrEqual(1);
  });

  test("schedule not due → tick does nothing", async ({
    page,
    request,
    seeded,
  }) => {
    // set hour/minute that almost certainly does not match the current UTC clock
    const now = new Date();
    const hour = (now.getUTCHours() + 12) % 24;

    await page.goto(`/repos/${seeded.repo_id}`);
    const card = page.getByTestId("schedule-card");
    await card.getByTestId("schedule-kind").selectOption("daily");
    await card.getByTestId("schedule-hour").fill(String(hour));
    await card.getByTestId("schedule-minute").fill("0");
    await page.getByRole("button", { name: /save changes/ }).click();
    await page.waitForTimeout(300);

    const r = await request.post(`${API_BASE}/test/scheduler/tick`);
    const body = await r.json();
    expect(body.scan_ids).toEqual([]);
  });

  test("disabled schedule cannot trigger anything", async ({
    page,
    request,
    seeded,
  }) => {
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("schedule-kind").selectOption("none");
    await page.getByRole("button", { name: /save changes/ }).click();
    await page.waitForTimeout(300);

    const r = await request.post(`${API_BASE}/test/scheduler/tick`);
    const body = await r.json();
    expect(body.scan_ids).toEqual([]);
  });
});
