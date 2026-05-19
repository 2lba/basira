import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, GitBranch } from "lucide-react";
import { listRepos } from "../api/client.js";
import OnboardingTour from "../components/OnboardingTour.jsx";
import EmptyState from "../components/ui/EmptyState.jsx";
import { SkeletonHeader, SkeletonRows } from "../components/ui/Skeleton.jsx";

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
    return <ReposEmpty />;
  }

  return (
    <section>
      <OnboardingTour />
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

function ReposEmpty() {
  return (
    <EmptyState
      testId="repos-empty"
      icon={<GitBranch size={22} />}
      title="no repositories yet"
      body="Install the reviewly GitHub App on a repository to get started."
      action={
        <a
          data-testid="install-app-link"
          href="https://github.com/apps/reviewly"
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
