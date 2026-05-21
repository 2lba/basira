// @ts-check
import { test as base, expect } from "@playwright/test";

const API_BASE = process.env.E2E_API_BASE || "http://localhost:8001";

async function resetState(request) {
  const res = await request.post(`${API_BASE}/test/reset`);
  if (!res.ok()) {
    throw new Error(`reset failed: ${res.status()} ${await res.text()}`);
  }
}

async function seedFixture(request, overrides = {}) {
  const res = await request.post(`${API_BASE}/test/seed`, {
    data: {
      github_login: "playwright-user",
      repo_full_name: "playwright-user/sample-repo",
      private: false,
      default_branch: "main",
      with_api_key: true,
      ...overrides,
    },
  });
  if (!res.ok()) {
    throw new Error(`seed failed: ${res.status()} ${await res.text()}`);
  }
  const body = await res.json();
  // copy auth cookies set by the seed response onto the browser context
  const setCookies = res.headersArray().filter((h) => h.name.toLowerCase() === "set-cookie");
  return { ...body, rawCookies: setCookies.map((h) => h.value) };
}

function parseSetCookie(raw, domain) {
  const [pair, ...attrs] = raw.split(";");
  const [name, ...valParts] = pair.split("=");
  const value = valParts.join("=").trim();
  const cookie = { name: name.trim(), value, domain, path: "/" };
  for (const attr of attrs) {
    const trimmed = attr.trim();
    if (/^httponly$/i.test(trimmed)) cookie.httpOnly = true;
    else if (/^secure$/i.test(trimmed)) cookie.secure = true;
    else if (/^samesite=(.+)$/i.test(trimmed)) {
      const m = trimmed.match(/^samesite=(.+)$/i);
      cookie.sameSite = capitalize(m[1]);
    } else if (/^path=(.+)$/i.test(trimmed)) {
      cookie.path = trimmed.split("=")[1];
    }
  }
  return cookie;
}

function capitalize(s) {
  const lo = s.toLowerCase();
  return lo[0].toUpperCase() + lo.slice(1);
}

export const test = base.extend({
  apiBase: [API_BASE, { option: true }],

  seeded: async ({ request, context }, use) => {
    await resetState(request);
    const seed = await seedFixture(request);
    const cookies = seed.rawCookies.map((raw) => parseSetCookie(raw, "localhost"));
    await context.addCookies(cookies);
    await use(seed);
  },
});

export { expect };

export async function seedWithoutApiKey(request, context) {
  await resetState(request);
  const seed = await seedFixture(request, { with_api_key: false });
  const cookies = seed.rawCookies.map((raw) => parseSetCookie(raw, "localhost"));
  await context.addCookies(cookies);
  return seed;
}

export async function finalizeScan(request, scanId) {
  const res = await request.post(`${API_BASE}/test/scans/${scanId}/finalize-now`);
  if (!res.ok()) {
    throw new Error(`finalize failed: ${res.status()} ${await res.text()}`);
  }
  return res.json();
}

export async function getScanList(request, repoId) {
  const res = await request.get(`${API_BASE}/api/repos/${repoId}/scans`);
  if (!res.ok()) {
    throw new Error(`list scans failed: ${res.status()}`);
  }
  return res.json();
}
