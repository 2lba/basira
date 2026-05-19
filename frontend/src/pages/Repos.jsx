import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, GitBranch } from "lucide-react";
import { listRepos } from "../api/client.js";

export default function Repos() {
  const [repos, setRepos] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listRepos()
      .then((data) => !cancelled && setRepos(data))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <ErrorBlock message={error} />;
  }
  if (repos === null) {
    return <SkeletonList />;
  }
  if (repos.length === 0) {
    return <EmptyState />;
  }

  return (
    <section>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">repositories</h1>
        <p className="mt-1 text-fg-secondary text-sm">
          {repos.length} {repos.length === 1 ? "repository" : "repositories"} connected
        </p>
      </div>
      <ul className="space-y-2">
        {repos.map((r) => (
          <li key={r.id}>
            <Link
              to={`/repos/${r.id}`}
              className="card flex items-center justify-between hover:border-border transition-colors"
            >
              <div className="flex items-center gap-3">
                <GitBranch size={16} className="text-fg-muted" />
                <div>
                  <div className="text-fg font-medium">{r.full_name}</div>
                  <div className="text-fg-muted text-xs mt-0.5">
                    {r.review_enabled ? "reviews enabled" : "reviews paused"} ·
                    threshold: {r.severity_threshold}
                  </div>
                </div>
              </div>
              <ChevronRight size={16} className="text-fg-muted" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function EmptyState() {
  return (
    <div className="card text-center py-16">
      <h2 className="text-lg font-medium">no repositories yet</h2>
      <p className="mt-2 text-fg-secondary text-sm">
        Install the reviewly GitHub App on a repository to get started.
      </p>
    </div>
  );
}

function SkeletonList() {
  return (
    <section>
      <div className="h-7 w-40 bg-surface rounded animate-pulse mb-6" />
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="card h-16 animate-pulse" />
        ))}
      </div>
    </section>
  );
}

function ErrorBlock({ message }) {
  return (
    <div className="card border-danger/40">
      <h2 className="text-lg font-medium text-danger">failed to load</h2>
      <p className="mt-1 text-fg-secondary text-sm">{message}</p>
    </div>
  );
}
