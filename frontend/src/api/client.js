const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function api(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body?.error?.message || `HTTP ${res.status}`);
    err.status = res.status;
    err.code = body?.error?.code;
    throw err;
  }
  return res.json();
}

export const health = () => api("/healthz");
export const ready = () => api("/readyz");

export const me = () => api("/auth/me");
export const logout = () => api("/auth/logout", { method: "POST" });
export const refreshSession = () => api("/auth/refresh", { method: "POST" });

export const githubLoginUrl = () => `${BASE}/auth/github/login`;

export const listRepos = () => api("/api/repos");
export const getRepo = (id) => api(`/api/repos/${id}`);
export const updateRepo = (id, body) =>
  api(`/api/repos/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const listReviews = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return api(`/api/reviews${q ? `?${q}` : ""}`);
};
export const getReview = (id) => api(`/api/reviews/${id}`);

export const startScan = (repoId) =>
  api(`/api/repos/${repoId}/scans`, { method: "POST" });
export const listRepoScans = (repoId) => api(`/api/repos/${repoId}/scans`);
export const listAllScans = () => api(`/api/scans`);
export const getScan = (id) => api(`/api/scans/${id}`);
export const compareScans = (a, b) =>
  api(`/api/scans/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);

export const createShare = (id) =>
  api(`/api/scans/${id}/share`, { method: "POST" });
export const revokeShare = (id) =>
  fetch(`${BASE}/api/scans/${id}/share`, {
    method: "DELETE",
    credentials: "include",
  }).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
  });
export const getPublicScan = (token) => api(`/share/${encodeURIComponent(token)}`);

export const getSmtp = () => api(`/api/me/smtp`);
export const updateSmtp = (body) =>
  api(`/api/me/smtp`, { method: "PATCH", body: JSON.stringify(body) });

export const getSlack = () => api(`/api/me/slack`);
export const updateSlack = (body) =>
  api(`/api/me/slack`, { method: "PATCH", body: JSON.stringify(body) });

export const getDiscord = () => api(`/api/me/discord`);
export const updateDiscord = (body) =>
  api(`/api/me/discord`, { method: "PATCH", body: JSON.stringify(body) });
