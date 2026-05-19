import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { GitPullRequest } from "lucide-react";
import { listReviews } from "../api/client.js";
import EmptyState from "../components/ui/EmptyState.jsx";
import { SkeletonHeader, SkeletonRows } from "../components/ui/Skeleton.jsx";

const PAGE = 25;

export default function Reviews() {
  const [items, setItems] = useState(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listReviews({ limit: PAGE, offset })
      .then((d) => !cancelled && setItems(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [offset]);

  if (error) return <p className="text-danger">{error}</p>;
  if (items === null) {
    return (
      <section data-testid="reviews-skeleton">
        <SkeletonHeader />
        <div className="mt-6">
          <SkeletonRows count={3} />
        </div>
      </section>
    );
  }
  if (items.length === 0 && offset === 0) {
    return (
      <EmptyState
        testId="reviews-empty"
        icon={<GitPullRequest size={22} />}
        title="no reviews yet"
        body="Open a pull request on a connected repo and basira will post AI feedback as comments."
      />
    );
  }

  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight">reviews</h1>
      <p className="mt-1 text-fg-secondary text-sm">
        Recent pull request reviews across your repositories
      </p>

      <div className="mt-6 card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border-subtle">
            <tr className="text-left text-fg-muted text-xs uppercase tracking-wider">
              <th className="px-4 py-3">repo</th>
              <th className="px-4 py-3">pr</th>
              <th className="px-4 py-3">status</th>
              <th className="px-4 py-3">findings</th>
              <th className="px-4 py-3">when</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id} className="border-b border-border-subtle last:border-0">
                <td className="px-4 py-3 font-mono text-xs">{r.repo_full_name}</td>
                <td className="px-4 py-3">
                  <Link
                    to={`/reviews/${r.id}`}
                    className="text-accent hover:underline"
                  >
                    #{r.pr_number} {r.pr_title}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <StatusPill status={r.status} />
                </td>
                <td className="px-4 py-3 text-fg-secondary">
                  <Counts counts={r.counts} />
                </td>
                <td className="px-4 py-3 text-fg-muted text-xs">
                  {new Date(r.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex gap-3 justify-end">
        <button
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE))}
          className="btn btn-ghost disabled:opacity-30"
        >
          previous
        </button>
        <button
          disabled={items.length < PAGE}
          onClick={() => setOffset(offset + PAGE)}
          className="btn btn-ghost disabled:opacity-30"
        >
          next
        </button>
      </div>
    </section>
  );
}

function StatusPill({ status }) {
  const tone =
    status === "posted" || status === "succeeded"
      ? "text-success"
      : status === "failed"
        ? "text-danger"
        : "text-fg-muted";
  return <span className={`font-mono text-xs ${tone}`}>{status}</span>;
}

function Counts({ counts }) {
  if (!counts || !counts.total) return <span>—</span>;
  return (
    <span className="font-mono text-xs">
      {counts.critical ? <span className="text-danger">{counts.critical}c </span> : null}
      {counts.major ? <span className="text-warning">{counts.major}M </span> : null}
      {counts.minor ? <span>{counts.minor}m </span> : null}
      {counts.nit ? <span className="text-fg-muted">{counts.nit}n</span> : null}
    </span>
  );
}
