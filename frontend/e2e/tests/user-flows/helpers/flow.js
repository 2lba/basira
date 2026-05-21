// shared helpers for the user-flow suite. they sit on top of the existing
// /test routes so each flow file can stay short and focused.
import { test as base, expect } from "@playwright/test";

const API_BASE = process.env.E2E_API_BASE || "http://localhost:8001";

export { expect };

function parseSetCookie(raw, domain) {
  const [pair, ...attrs] = raw.split(";");
  const [name, ...valParts] = pair.split("=");
  const value = valParts.join("=").trim();
  const cookie = { name: name.trim(), value, domain, path: "/" };
  for (const a of attrs) {
    const t = a.trim();
    if (/^httponly$/i.test(t)) cookie.httpOnly = true;
    else if (/^secure$/i.test(t)) cookie.secure = true;
    else if (/^samesite=(.+)$/i.test(t)) {
      cookie.sameSite =
        t.slice("samesite=".length, t.length).replace(/^./, (c) => c.toUpperCase());
    } else if (/^path=(.+)$/i.test(t)) cookie.path = t.split("=")[1];
  }
  return cookie;
}

async function applyCookies(context, rawCookies) {
  const cookies = rawCookies.map((raw) => parseSetCookie(raw, "localhost"));
  await context.addCookies(cookies);
}

export async function resetState(request) {
  const r = await request.post(`${API_BASE}/test/reset`);
  if (!r.ok()) throw new Error(`reset failed: ${r.status()}`);
}

export async function seedUser(request, context, opts = {}) {
  const res = await request.post(`${API_BASE}/test/seed`, {
    data: {
      github_login: opts.login || "playwright-user",
      repo_full_name: opts.repo || "playwright-user/sample-repo",
      private: false,
      default_branch: "main",
      with_api_key: opts.withKey !== false,
    },
  });
  if (!res.ok()) throw new Error(`seed failed: ${res.status()} ${await res.text()}`);
  const body = await res.json();
  const setCookies = res.headersArray()
    .filter((h) => h.name.toLowerCase() === "set-cookie")
    .map((h) => h.value);
  if (context) await applyCookies(context, setCookies);
  return { ...body, rawCookies: setCookies };
}

export async function finalizeScan(request, scanId) {
  const r = await request.post(`${API_BASE}/test/scans/${scanId}/finalize-now`);
  if (!r.ok()) throw new Error(`finalize failed: ${r.status()}`);
  return r.json();
}

export async function listScansForRepo(request, repoId) {
  const r = await request.get(`${API_BASE}/api/repos/${repoId}/scans`);
  if (!r.ok()) throw new Error(`list scans failed: ${r.status()}`);
  return r.json();
}

export async function startScanViaApi(request, repoId) {
  const r = await request.post(`${API_BASE}/api/repos/${repoId}/scans`);
  if (!r.ok()) throw new Error(`start scan failed: ${r.status()}`);
  return r.json();
}

export async function getScan(request, scanId) {
  const r = await request.get(`${API_BASE}/api/scans/${scanId}`);
  if (!r.ok()) throw new Error(`get scan failed: ${r.status()}`);
  return r.json();
}

export async function waitForScanStatus(
  request,
  scanId,
  target,
  timeoutMs = 30_000,
) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const s = await getScan(request, scanId);
    if (s.status === target) return s;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`scan ${scanId} did not reach ${target} in ${timeoutMs}ms`);
}

export async function revokeKey(request, userId) {
  const r = await request.post(`${API_BASE}/test/revoke-key/${userId}`);
  if (!r.ok()) throw new Error(`revoke-key failed: ${r.status()}`);
  return r.json();
}

export async function orphanRunningScans(request) {
  const r = await request.post(`${API_BASE}/test/scans/orphan-running`);
  if (!r.ok()) throw new Error(`orphan-running failed: ${r.status()}`);
  return r.json();
}

export async function getWebhookSink(request, kind) {
  const r = await request.get(`${API_BASE}/test/webhook-sink/${kind}`);
  if (!r.ok()) throw new Error(`sink get failed: ${r.status()}`);
  return r.json();
}

export async function clearWebhookSink(request, kind) {
  const r = await request.post(`${API_BASE}/test/webhook-sink/${kind}/clear`);
  if (!r.ok()) throw new Error(`sink clear failed: ${r.status()}`);
  return r.json();
}

export const test = base.extend({
  apiBase: [API_BASE, { option: true }],
  cleanState: async ({ request }, use) => {
    await resetState(request);
    await use(undefined);
  },
});
