// @ts-check
import { test, expect } from "./fixtures.js";

test.describe("about page", () => {
  test("renders product info and links", async ({ page, seeded: _seeded }) => {
    await page.goto("/about");
    await expect(page.getByTestId("about-page")).toBeVisible();
    await expect(page.locator("body")).toContainText("version 0.1.0");
    await expect(page.locator("body")).toContainText(/Basira is/);
    await expect(page.locator("body")).toContainText(/Abdulaziz AlQahtani/);

    const github = page.getByTestId("about-github");
    await expect(github).toHaveAttribute(
      "href",
      "https://github.com/2lba/basira",
    );
    const author = page.getByTestId("about-author");
    await expect(author).toHaveAttribute("href", "https://github.com/2lba");
  });

  test("reachable from sidebar", async ({ page, seeded: _seeded }) => {
    await page.goto("/");
    await page.getByRole("link", { name: /about/i }).click();
    await expect(page).toHaveURL(/\/about$/);
    await expect(page.getByTestId("about-page")).toBeVisible();
  });
});
