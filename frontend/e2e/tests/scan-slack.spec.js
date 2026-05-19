// @ts-check
import { test, expect } from "./fixtures.js";

const API_BASE = process.env.E2E_API_BASE || "http://localhost:8001";
const BACKEND_INTERNAL = "http://backend:8000";

test.describe("slack webhook", () => {
  test("save webhook + enable; scan posts a Slack payload", async ({
    page,
    request,
    seeded,
  }) => {
    await request.post(`${API_BASE}/test/webhook-sink/slack/clear`);

    await page.goto("/settings");
    const card = page.getByTestId("slack-card");
    await expect(card).toBeVisible();

    // toggle disabled initially
    await expect(card.getByTestId("slack-card-enabled")).toBeDisabled();

    // backend reaches the sink through the docker network hostname
    const sinkUrl = `${BACKEND_INTERNAL}/test/webhook-sink/slack`;
    await card.getByTestId("slack-card-url").fill(sinkUrl);
    await card.getByTestId("slack-card-enabled").check();
    await card.getByTestId("slack-card-save").click();
    await expect(card.getByTestId("slack-card-status")).toContainText("saved", {
      timeout: 5_000,
    });
    await expect(card.getByTestId("slack-card-stored")).toBeVisible();

    // run a scan
    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();
    await page
      .getByTestId("scan-history")
      .locator("a")
      .first()
      .waitFor({ state: "visible", timeout: 25_000 });

    // poll the sink
    await expect.poll(
      async () => {
        const r = await request.get(`${API_BASE}/test/webhook-sink/slack`);
        const body = await r.json();
        return body.payload;
      },
      { timeout: 10_000 },
    ).not.toBeNull();

    const r = await request.get(`${API_BASE}/test/webhook-sink/slack`);
    const body = await r.json();
    expect(body.payload.text).toContain("playwright-user/sample-repo");
    expect(JSON.stringify(body.payload)).toMatch(/Score:\*?\\?\*?\s*\d+\/100/);
    expect(Array.isArray(body.payload.blocks)).toBe(true);
  });

  test("clearing the webhook also disables notifications", async ({
    page,
    request,
    seeded: _seeded,
  }) => {
    const sinkUrl = `${BACKEND_INTERNAL}/test/webhook-sink/slack`;
    await page.goto("/settings");
    const card = page.getByTestId("slack-card");
    await card.getByTestId("slack-card-url").fill(sinkUrl);
    await card.getByTestId("slack-card-enabled").check();
    await card.getByTestId("slack-card-save").click();
    await expect(card.getByTestId("slack-card-stored")).toBeVisible();

    await card.getByTestId("slack-card-clear").click();
    await expect(card.getByTestId("slack-card-status")).toContainText("cleared");
    await expect(card.getByTestId("slack-card-stored")).not.toBeVisible();
    await expect(card.getByTestId("slack-card-enabled")).not.toBeChecked();
  });
});
