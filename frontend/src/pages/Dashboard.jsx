import { useEffect, useState } from "react";
import { Activity, LogOut } from "lucide-react";
import { health, ready, logout } from "../api/client.js";

export default function Dashboard({ user, onLogout }) {
  const [status, setStatus] = useState({ api: "checking", db: "checking" });

  useEffect(() => {
    let cancelled = false;
    Promise.all([health().catch(() => null), ready().catch(() => null)]).then(
      ([h, r]) => {
        if (cancelled) return;
        setStatus({
          api: h?.status === "ok" ? "ok" : "down",
          db: r?.db === "up" ? "ok" : "down",
        });
      }
    );
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleLogout() {
    try {
      await logout();
    } finally {
      onLogout?.();
    }
  }

  return (
    <div className="min-h-full">
      <header className="border-b border-border-subtle">
        <div className="max-w-content mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-fg font-semibold tracking-tight">basira</span>
            <span className="text-fg-muted text-xs">v0.1.0</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm">
              {user.avatar_url && (
                <img
                  src={user.avatar_url}
                  alt=""
                  className="w-6 h-6 rounded-full border border-border-subtle"
                />
              )}
              <span className="text-fg-secondary">{user.github_login}</span>
            </div>
            <button
              onClick={handleLogout}
              className="btn btn-ghost"
              aria-label="sign out"
            >
              <LogOut size={16} />
              <span>sign out</span>
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-content mx-auto px-6 py-16">
        <section className="max-w-2xl">
          <h1 className="text-2xl font-semibold tracking-tight">
            welcome back, {user.github_login}
          </h1>
          <p className="mt-2 text-fg-secondary leading-relaxed">
            No repositories enabled yet. Install the GitHub App to start
            reviewing PRs.
          </p>
        </section>

        <section className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatusCard label="api" value={status.api} />
          <StatusCard label="database" value={status.db} />
          <StatusCard label="worker" value="pending" />
        </section>
      </main>
    </div>
  );
}

function StatusCard({ label, value }) {
  const tone =
    value === "ok"
      ? "text-success"
      : value === "down"
        ? "text-danger"
        : "text-fg-muted";
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <span className="text-fg-secondary text-sm">{label}</span>
        <Activity size={14} className={tone} aria-hidden="true" />
      </div>
      <div className={`mt-2 text-lg font-mono ${tone}`}>{value}</div>
    </div>
  );
}
