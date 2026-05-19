import { useEffect, useState } from "react";
import { Activity, Github } from "lucide-react";
import { health, ready } from "./api/client.js";

export default function App() {
  const [status, setStatus] = useState({ api: "checking", db: "checking" });
  const [error, setError] = useState(null);

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
    ).catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-full">
      <header className="border-b border-border-subtle">
        <div className="max-w-content mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-fg font-semibold tracking-tight">reviewly</span>
            <span className="text-fg-muted text-xs">v0.1.0</span>
          </div>
          <a
            href="https://github.com/2lba/reviewly"
            className="btn btn-ghost"
            aria-label="open repository on github"
          >
            <Github size={16} />
            <span>github</span>
          </a>
        </div>
      </header>

      <main className="max-w-content mx-auto px-6 py-16">
        <section className="max-w-2xl">
          <h1 className="text-4xl font-semibold tracking-tight">
            AI code reviews. Open source. Self-hosted.
          </h1>
          <p className="mt-4 text-fg-secondary leading-relaxed">
            Senior engineer feedback on every PR, running on your infra.
          </p>
        </section>

        <section className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatusCard label="api" value={status.api} />
          <StatusCard label="database" value={status.db} />
          <StatusCard label="worker" value="pending" />
        </section>

        {error && (
          <p className="mt-8 text-danger text-sm" role="alert">
            {error}
          </p>
        )}
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
