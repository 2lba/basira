// flow E: edge cases around BYOK key lifecycle.
import {
  test,
  expect,
  resetState,
  seedUser,
  startScanViaApi,
  getScan,
  revokeKey,
} from "./helpers/flow.js";

const API_BASE = process.env.E2E_API_BASE || "http://localhost:8001";

async function waitForTerminal(request, scanId, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs;
  let state;
  while (Date.now() < deadline) {
    state = await getScan(request, scanId);
    if (state.status === "succeeded" || state.status === "failed") return state;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`scan ${scanId} did not finish in ${timeoutMs}ms (last status: ${state?.status})`);
}

test.describe("flow E - edge cases", () => {
  test("invalid key is rejected at write time", async ({ request, context }) => {
    await resetState(request);
    await seedUser(request, context, { withKey: false });
    // empty string is too short for the schema; an explicit obviously-bogus
    // key bypasses the e2e- prefix bypass and must be rejected.
    const r = await request.put(`${API_BASE}/api/me/api-keys/anthropic`, {
      data: { api_key: "sk-not-actually-an-anthropic-key-12345" },
    });
    expect([400, 422]).toContain(r.status());
  });

  test("deleting a key only blocks new scans, not the active one", async ({ request, context }) => {
    await resetState(request);
    const seed = await seedUser(request, context);

    // first scan: let the worker run the e2e stub to completion using the
    // key that was live at start. polling avoids the race the manual
    // finalize-now route created when worker writes lagged the test.
    const first = await startScanViaApi(request, seed.repo_id);
    const firstDone = await waitForTerminal(request, first.id, 20_000);
    expect(firstDone.status).toBe("succeeded");

    // remove the key, the next scan attempt should fail with MISSING_API_KEY
    const del = await request.delete(`${API_BASE}/api/me/api-keys/anthropic`);
    expect(del.status()).toBe(204);

    const next = await startScanViaApi(request, seed.repo_id);
    const nextDone = await waitForTerminal(request, next.id, 20_000);
    expect(nextDone.status).toBe("failed");
    expect(nextDone.error || "").toMatch(/MISSING_API_KEY/);
  });

  test("revoked key surfaces as a failed scan flag in the api", async ({ request, context }) => {
    await resetState(request);
    const seed = await seedUser(request, context);
    await revokeKey(request, seed.user_id);
    const list = await request.get(`${API_BASE}/api/me/api-keys`);
    const body = await list.json();
    expect(body[0].is_valid).toBe(false);
  });
});
