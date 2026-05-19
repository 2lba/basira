// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("email setup UX", () => {
  test("email card shows Optional badge and the alternatives hint", async ({
    page,
    seeded: _seeded,
  }) => {
    await page.goto("/settings/notifications");
    const card = page.getByTestId("smtp-card");
    await expect(card).toBeVisible();
    await expect(card.getByTestId("smtp-optional-badge")).toContainText(
      /Optional/,
    );
    await expect(card.getByTestId("smtp-alternatives-hint")).toContainText(
      /Slack or Discord/i,
    );
  });

  test("how-to-set-this-up guide expands and explains the fields", async ({
    page,
    seeded: _seeded,
  }) => {
    await page.goto("/settings/notifications");
    const card = page.getByTestId("smtp-card");
    const toggle = card.getByTestId("smtp-guide-toggle");
    await expect(toggle).toBeVisible();
    await expect(card.getByTestId("smtp-guide-body")).toHaveCount(0);

    await toggle.click();
    const body = card.getByTestId("smtp-guide-body");
    await expect(body).toBeVisible();
    await expect(body).toContainText("smtp.gmail.com");
    await expect(body).toContainText("Resend");
    await expect(body).toContainText("3000 emails");
  });

  test("notify checkbox is disabled with a clear message when SMTP not configured", async ({
    page,
    seeded: _seeded,
  }) => {
    await page.goto("/settings/notifications");
    const card = page.getByTestId("smtp-card");
    const toggle = card.getByTestId("notify-enabled");
    await expect(toggle).toBeDisabled();
    await expect(card.getByTestId("smtp-disabled-hint")).toContainText(
      "Configure SMTP first",
    );

    // filling the fields enables the checkbox
    await card.getByTestId("smtp-host").fill("smtp.example.com");
    await card.getByTestId("smtp-port").fill("587");
    await card.getByTestId("smtp-from").fill("alerts@example.com");
    await expect(toggle).toBeEnabled();
  });
});
