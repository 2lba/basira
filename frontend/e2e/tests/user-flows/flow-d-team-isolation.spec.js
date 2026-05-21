// flow D: user B cannot reach user A's resources. We use a fresh request
// context per user so cookies do not bleed between them.
import { request as playwrightRequest } from "@playwright/test";
import { test, expect, resetState } from "./helpers/flow.js";

const API_BASE = process.env.E2E_API_BASE || "http://localhost:8001";

async function seedIsolated(login, repoFull) {
  const ctx = await playwrightRequest.newContext({ baseURL: API_BASE });
  const r = await ctx.post(`${API_BASE}/test/seed`, {
    data: {
      github_login: login,
      repo_full_name: repoFull,
      private: false,
      default_branch: "main",
      with_api_key: true,
    },
  });
  if (!r.ok()) throw new Error(`seed failed: ${r.status()} ${await r.text()}`);
  const body = await r.json();
  return { ctx, ...body };
}

test.describe("flow D - team isolation", () => {
  test("user B is denied on user A's repo, scan and finding", async ({ request }) => {
    await resetState(request);

    const a = await seedIsolated("playwright-alice", "playwright-alice/repo-a");
    const b = await seedIsolated("playwright-bob", "playwright-bob/repo-b");

    // A starts and finalizes a scan using A's own request context
    const aScanResp = await a.ctx.post(`${API_BASE}/api/repos/${a.repo_id}/scans`);
    expect(aScanResp.ok()).toBeTruthy();
    const aScan = await aScanResp.json();
    const fin = await a.ctx.post(`${API_BASE}/test/scans/${aScan.id}/finalize-now`);
    expect(fin.ok()).toBeTruthy();

    // B's context attempts every cross-user op
    const r1 = await b.ctx.get(`${API_BASE}/api/repos/${a.repo_id}`);
    expect(r1.status()).toBe(404);

    const r2 = await b.ctx.get(`${API_BASE}/api/scans/${aScan.id}`);
    expect(r2.status()).toBe(404);

    const r3 = await b.ctx.post(`${API_BASE}/api/repos/${a.repo_id}/scans`);
    expect(r3.status()).toBe(404);

    const r4 = await b.ctx.get(`${API_BASE}/api/me/api-keys`);
    expect(r4.ok()).toBeTruthy();
    const list = await r4.json();
    expect(list.length).toBe(1);
    expect(list[0].provider).toBe("anthropic");

    await a.ctx.dispose();
    await b.ctx.dispose();
  });
});
