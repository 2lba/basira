import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { ChevronRight, GitBranch } from "lucide-react";
import { listRepos } from "../api/client.js";
import OnboardingTour from "../components/OnboardingTour.jsx";
import EmptyState from "../components/ui/EmptyState.jsx";
import { SkeletonHeader, SkeletonRows } from "../components/ui/Skeleton.jsx";

export default function Repos() {
  const { user } = useOutletContext() || {};
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
  const installUrl = user?.install_url || "#";

  if (repos.length === 0) {
    return <ReposEmpty installUrl={installUrl} />;
  }

  const connectedCount = repos.filter((r) => r.connected).length;
  const unconnectedCount = repos.length - connectedCount;

  return (
    <section>
      <OnboardingTour />
      <div className="mb-6 flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">repositories</h1>
          <p className="mt-1 text-fg-secondary text-sm">
            {connectedCount} connected · {unconnectedCount} not yet connected
          </p>
        </div>
      </div>
      <ul className="space-y-2">
        {repos.map((r) =>
          r.connected ? (
            <li key={r.id}>
              <Link
                to={`/repos/${r.id}`}
                data-testid="repo-row-connected"
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
          ) : (
            <li
              key={r.id}
              data-testid="repo-row-unconnected"
              className="card flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <GitBranch size={16} className="text-fg-muted" />
                <div>
                  <div className="text-fg font-medium">{r.full_name}</div>
                  <div className="text-fg-muted text-xs mt-0.5">
                    not connected - install the app to enable scans
                  </div>
                </div>
              </div>
              <a
                data-testid="connect-repo-link"
                href={installUrl}
                target="_blank"
                rel="noreferrer noopener"
                className="btn btn-primary"
              >
                connect
              </a>
            </li>
          ),
        )}
      </ul>
    </section>
  );
}

function ReposEmpty({ installUrl }) {
  return (
    <EmptyState
      testId="repos-empty"
      icon={<GitBranch size={22} />}
      title="no repositories yet"
      body="Install the GitHub App on a repository to get started."
      action={
        <a
          data-testid="install-app-link"
          href={installUrl}
          target="_blank"
          rel="noreferrer noopener"
          className="btn btn-primary"
        >
          install on GitHub
        </a>
      }
    />
  );
}

function SkeletonList() {
  return (
    <section data-testid="repos-skeleton">
      <SkeletonHeader />
      <div className="mt-6">
        <SkeletonRows count={3} />
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
