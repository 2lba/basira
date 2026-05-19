// @ts-check
import { test, expect } from "./fixtures.js";

const API_BASE = process.env.E2E_API_BASE || "http://localhost:8001";

test.describe("install url + repo connection state", () => {
  test("install URL is in /auth/me and built from config", async ({
    request,
    seeded: _seeded,
  }) => {
    const r = await request.get(`${API_BASE}/auth/me`);
    expect(r.ok()).toBe(true);
    const body = await r.json();
    expect(body.install_url).toMatch(
      /^https:\/\/github\.com\/apps\/[^/]+\/installations\/new$/,
    );
  });

  test("repos endpoint includes both connected and non-connected repos", async ({
    request,
    page,
  }) => {
    // seed with one connected + two unconnected repos
    await request.post(`${API_BASE}/test/reset`);
    const seedRes = await request.post(`${API_BASE}/test/seed`, {
      data: {
        github_login: "playwright-user",
        repo_full_name: "playwright-user/sample-repo",
        extra_unconnected: [
          "playwright-user/another-repo",
          "playwright-user/third-repo",
        ],
      },
    });
    const seed = await seedRes.json();
    const setCookies = seedRes
      .headersArray()
      .filter((h) => h.name.toLowerCase() === "set-cookie")
      .map((h) => h.value);
    const cookies = setCookies.map((raw) => {
      const [pair, ...attrs] = raw.split(";");
      const [name, ...valParts] = pair.split("=");
      const c = {
        name: name.trim(),
        value: valParts.join("=").trim(),
        domain: "localhost",
        path: "/",
      };
      for (const a of attrs) {
        const t = a.trim();
        if (/^path=(.+)$/i.test(t)) c.path = t.split("=")[1];
      }
      return c;
    });
    await page.context().addCookies(cookies);

    const repos = await (await request.get(`${API_BASE}/api/repos`)).json();
    expect(repos).toHaveLength(3);
    const connected = repos.filter((r) => r.connected);
    const unconnected = repos.filter((r) => !r.connected);
    expect(connected).toHaveLength(1);
    expect(unconnected).toHaveLength(2);

    // verify UI distinguishes them
    await page.goto("/");
    await expect(page.getByTestId("repo-row-connected")).toHaveCount(1);
    await expect(page.getByTestId("repo-row-unconnected")).toHaveCount(2);
    const connect = page.getByTestId("connect-repo-link").first();
    await expect(connect).toBeVisible();
    const href = await connect.getAttribute("href");
    expect(href).toMatch(/\/apps\/[^/]+\/installations\/new$/);

    // starting a scan on an unconnected repo is blocked by the API
    const scanRes = await request.post(
      `${API_BASE}/api/repos/${seed.unconnected_repo_ids[0]}/scans`,
    );
    expect(scanRes.status()).toBe(409);
  });

  test("repo detail disables scan button when not connected", async ({
    page,
    request,
  }) => {
    await request.post(`${API_BASE}/test/reset`);
    const seedRes = await request.post(`${API_BASE}/test/seed`, {
      data: {
        github_login: "playwright-user",
        repo_full_name: "playwright-user/sample-repo",
        extra_unconnected: ["playwright-user/another-repo"],
      },
    });
    const seed = await seedRes.json();
    const setCookies = seedRes
      .headersArray()
      .filter((h) => h.name.toLowerCase() === "set-cookie")
      .map((h) => h.value);
    const cookies = setCookies.map((raw) => {
      const [pair, ...attrs] = raw.split(";");
      const [name, ...valParts] = pair.split("=");
      const c = {
        name: name.trim(),
        value: valParts.join("=").trim(),
        domain: "localhost",
        path: "/",
      };
      for (const a of attrs) {
        const t = a.trim();
        if (/^path=(.+)$/i.test(t)) c.path = t.split("=")[1];
      }
      return c;
    });
    await page.context().addCookies(cookies);

    const unconnectedId = seed.unconnected_repo_ids[0];
    await page.goto(`/repos/${unconnectedId}`);
    const scanBtn = page.getByTestId("scan-now");
    await expect(scanBtn).toBeDisabled();
    await expect(scanBtn).toContainText(/install to scan/);
  });
});
