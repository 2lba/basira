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
