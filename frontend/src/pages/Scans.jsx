import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAllScans } from "../api/client.js";
import { ScoreCircle, CountsInline } from "../components/features/ScanCard.jsx";

const ACTIVE = new Set(["pending", "running"]);

export default function Scans() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let timer;

    async function load() {
      try {
        const data = await listAllScans();
        if (cancelled) return;
        setItems(data);
        if (data.some((s) => ACTIVE.has(s.status))) {
          timer = setTimeout(load, 2000);
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }
    load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (error) return <p className="text-danger">{error}</p>;
  if (items === null) {
    return <div className="h-32 bg-surface rounded-card animate-pulse" />;
  }
  if (items.length === 0) {
    return (
      <div className="card text-center py-16">
        <h2 className="text-lg font-medium">no scans yet</h2>
        <p className="mt-2 text-fg-secondary text-sm">
          Open a repository and click "scan now" to run one.
        </p>
      </div>
    );
  }

  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight">scans</h1>
      <p className="mt-1 text-fg-secondary text-sm">
        Repository-wide audits across your connected repos
      </p>

      <ul className="mt-6 space-y-2">
        {items.map((s) => (
          <li key={s.id}>
            <Link
              to={`/scans/${s.id}`}
              className="card flex items-center justify-between hover:border-border transition-colors"
            >
              <div className="flex items-center gap-4">
                <ScoreCircle score={s.score} size={56} />
                <div>
                  <div className="text-fg font-medium font-mono text-sm">
                    {s.repo_full_name}
                  </div>
                  <div className="text-fg-muted text-xs mt-0.5">
                    {s.summary || s.progress_message || s.status}
                  </div>
                  <div className="text-fg-muted text-xs mt-1 font-mono">
                    {new Date(s.created_at).toLocaleString()}
                  </div>
                </div>
              </div>
              <CountsInline counts={s.counts} status={s.status} />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
