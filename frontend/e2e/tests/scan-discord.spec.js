// @ts-check
import { test, expect } from "./fixtures.js";

const API_BASE = process.env.E2E_API_BASE || "http://localhost:8001";
const BACKEND_INTERNAL = "http://backend:8000";

test.describe("discord webhook", () => {
  test("save webhook + enable; scan posts a Discord embed", async ({
    page,
    request,
    seeded,
  }) => {
    await request.post(`${API_BASE}/test/webhook-sink/discord/clear`);

    await page.goto("/settings");
    const card = page.getByTestId("discord-card");
    await expect(card).toBeVisible();
    await expect(card.getByTestId("discord-card-enabled")).toBeDisabled();

    const sinkUrl = `${BACKEND_INTERNAL}/test/webhook-sink/discord`;
    await card.getByTestId("discord-card-url").fill(sinkUrl);
    await card.getByTestId("discord-card-enabled").check();
    await card.getByTestId("discord-card-save").click();
    await expect(card.getByTestId("discord-card-status")).toContainText("saved", {
      timeout: 5_000,
    });

    await page.goto(`/repos/${seeded.repo_id}`);
    await page.getByTestId("scan-now").click();
    await page
      .getByTestId("scan-history")
      .locator("a")
      .first()
      .waitFor({ state: "visible", timeout: 25_000 });

    await expect.poll(
      async () => {
        const r = await request.get(`${API_BASE}/test/webhook-sink/discord`);
        const body = await r.json();
        return body.payload;
      },
      { timeout: 10_000 },
    ).not.toBeNull();

    const r = await request.get(`${API_BASE}/test/webhook-sink/discord`);
    const body = await r.json();
    const payload = body.payload;
    expect(Array.isArray(payload.embeds)).toBe(true);
    const embed = payload.embeds[0];
    expect(embed.title).toContain("playwright-user/sample-repo");
    expect(typeof embed.color).toBe("number");
    expect(embed.url).toMatch(/\/scans\/[0-9a-f-]{36}$/);
    const scoreField = embed.fields.find((f) => f.name === "Score");
    expect(scoreField).toBeTruthy();
    expect(scoreField.value).toMatch(/\d+\/100/);
    const findingsField = embed.fields.find((f) => f.name === "Findings");
    expect(findingsField.value).toMatch(/\d+ critical|0 findings/);
  });

  test("toggle disabled until webhook url is set", async ({
    page,
    seeded: _seeded,
  }) => {
    await page.goto("/settings");
    const card = page.getByTestId("discord-card");
    const toggle = card.getByTestId("discord-card-enabled");
    await expect(toggle).toBeDisabled();
    await card.getByTestId("discord-card-url").fill("https://discord.com/api/x");
    await expect(toggle).toBeEnabled();
  });
});
