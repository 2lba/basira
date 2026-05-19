// @ts-check
import { test, expect } from "./fixtures.js";

const API_BASE = process.env.E2E_API_BASE || "http://localhost:8001";

test.describe("email notification on scan finish", () => {
  test("when SMTP not configured no email is sent", async ({
    page,
    request,
    seeded,
  }) => {
    await request.post(`${API_BASE}/test/last-email/clear`);

    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();
    await page
      .getByTestId("scan-history")
      .locator("a")
      .first()
      .waitFor({ state: "visible", timeout: 25_000 });

    // wait a beat for the worker to flush the (non-)notify step
    await page.waitForTimeout(800);
    const r = await request.get(`${API_BASE}/test/last-email`);
    const body = await r.json();
    expect(body.email).toBeNull();
  });

  test("configuring SMTP and enabling notifications sends an email", async ({
    page,
    request,
    seeded,
  }) => {
    await request.post(`${API_BASE}/test/last-email/clear`);

    await page.goto("/settings/notifications");
    const card = page.getByTestId("smtp-card");
    await expect(card).toBeVisible();

    // initially the notify toggle is disabled because the form is empty
    await expect(page.getByTestId("notify-enabled")).toBeDisabled();

    await page.getByTestId("smtp-host").fill("smtp.example.com");
    await page.getByTestId("smtp-port").fill("587");
    await page.getByTestId("smtp-from").fill("alerts@example.com");
    await page.getByTestId("smtp-username").fill("playwright-user");
    await page.getByTestId("smtp-password").fill("hunter2");
    await page.getByTestId("notify-enabled").check();
    await page.getByTestId("smtp-save").click();

    await expect(page.getByTestId("smtp-status")).toContainText("saved", {
      timeout: 5_000,
    });

    // run a scan
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();
    await page
      .getByTestId("scan-history")
      .locator("a")
      .first()
      .waitFor({ state: "visible", timeout: 25_000 });

    // poll the e2e stash for the email
    await expect.poll(
      async () => {
        const r = await request.get(`${API_BASE}/test/last-email`);
        const body = await r.json();
        return body.email;
      },
      { timeout: 10_000 },
    ).not.toBeNull();

    const r = await request.get(`${API_BASE}/test/last-email`);
    const body = await r.json();
    expect(body.email.from).toBe("alerts@example.com");
    expect(body.email.subject).toContain("playwright-user/sample-repo");
    expect(body.email.subject).toMatch(/score \d+\/100/i);
    expect(body.email.body).toContain("View report:");
  });

  test("notifications toggle stays disabled if smtp fields are blank", async ({
    page,
    seeded: _seeded,
  }) => {
    await page.goto("/settings/notifications");
    const toggle = page.getByTestId("notify-enabled");
    await expect(toggle).toBeDisabled();
    // filling only host still keeps it disabled
    await page.getByTestId("smtp-host").fill("smtp.example.com");
    await expect(toggle).toBeDisabled();
  });
});
