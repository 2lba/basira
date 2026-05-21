// flow C: configure slack + discord webhooks, verify the sink receives a
// delivery once a scan finishes.
import {
  test,
  expect,
  resetState,
  seedUser,
  startScanViaApi,
  getScan,
  getWebhookSink,
  clearWebhookSink,
} from "./helpers/flow.js";

const API_BASE = process.env.E2E_API_BASE || "http://localhost:8001";
// the webhook validator blocks loopback hosts, so we go through the docker
// network hostname when configuring the sink URL.
const BACKEND_INTERNAL = "http://backend:8000";

async function configureWebhook(request, kind, url) {
  const r = await request.patch(`${API_BASE}/api/me/${kind}`, {
    data: { url, enabled: true },
  });
  if (!r.ok()) throw new Error(`${kind} configure failed: ${r.status()} ${await r.text()}`);
  return r.json();
}

async function waitForTerminal(request, scanId, timeoutMs = 25_000) {
  const deadline = Date.now() + timeoutMs;
  let state;
  while (Date.now() < deadline) {
    state = await getScan(request, scanId);
    if (state.status === "succeeded" || state.status === "failed") return state;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`scan ${scanId} did not finish in ${timeoutMs}ms`);
}

test.describe("flow C - notifications", () => {
  test("slack + discord receive a delivery after a scan completes", async ({ page, request, context }) => {
    await resetState(request);
    const seed = await seedUser(request, context);
    await clearWebhookSink(request, "slack");
    await clearWebhookSink(request, "discord");

    await configureWebhook(request, "slack", `${BACKEND_INTERNAL}/test/webhook-sink/slack`);
    await configureWebhook(request, "discord", `${BACKEND_INTERNAL}/test/webhook-sink/discord`);

    await page.goto("/settings/notifications");
    await expect(page.getByTestId("notifications-tab")).toBeVisible();
    await expect(page.getByTestId("slack-card-stored")).toBeVisible();
    await expect(page.getByTestId("discord-card-stored")).toBeVisible();

    // start scan, let the worker run the e2e stub to terminal state - that
    // is what wires the notifier delivery.
    const scan = await startScanViaApi(request, seed.repo_id);
    const done = await waitForTerminal(request, scan.id);
    expect(done.status).toBe("succeeded");

    // poll the sinks
    const deadline = Date.now() + 15_000;
    let slack, discord;
    while (Date.now() < deadline) {
      slack = (await getWebhookSink(request, "slack")).payload;
      discord = (await getWebhookSink(request, "discord")).payload;
      if (slack && discord) break;
      await new Promise((r) => setTimeout(r, 500));
    }
    expect(slack, "slack sink should have received a payload").toBeTruthy();
    expect(discord, "discord sink should have received a payload").toBeTruthy();
  });
});
