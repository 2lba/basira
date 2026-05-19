import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { getReview } from "../api/client.js";

export default function ReviewDetail() {
  const { id } = useParams();
  const [r, setR] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getReview(id)
      .then((d) => !cancelled && setR(d))
      .catch((e) => !cancelled && setErr(e.message));
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (err) return <p className="text-danger">{err}</p>;
  if (!r) return <p className="text-fg-muted">loading...</p>;

  return (
    <section>
      <Link to="/reviews" className="btn btn-ghost mb-4">
        <ArrowLeft size={14} />
        <span>back to reviews</span>
      </Link>

      <h1 className="text-2xl font-semibold tracking-tight">
        #{r.pr_number} {r.pr_title}
      </h1>
      <p className="mt-1 text-fg-secondary text-sm font-mono">
        {r.repo_full_name} · {r.head_sha.slice(0, 7)} · {r.model || "default"}
      </p>

      <div className="mt-6 card">
        <h2 className="text-sm uppercase tracking-wider text-fg-muted">summary</h2>
        <p className="mt-2 text-fg leading-relaxed">{r.summary || "—"}</p>
        {r.error && (
          <p className="mt-3 text-danger text-sm font-mono">{r.error}</p>
        )}
        <dl className="mt-4 grid grid-cols-3 gap-4 text-xs text-fg-muted">
          <Stat label="status" value={r.status} />
          <Stat
            label="tokens"
            value={
              r.tokens_input != null
                ? `${r.tokens_input} in / ${r.tokens_output ?? 0} out`
                : "—"
            }
          />
          <Stat
            label="cost"
            value={r.cost_usd != null ? `$${r.cost_usd.toFixed(4)}` : "—"}
          />
        </dl>
      </div>

      <h2 className="mt-8 text-sm uppercase tracking-wider text-fg-muted">
        comments ({r.comments.length})
      </h2>
      {r.comments.length === 0 ? (
        <p className="mt-4 text-fg-secondary">No issues found.</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {r.comments.map((c) => (
            <li key={c.id} className="card">
              <div className="flex items-center gap-3 flex-wrap">
                <SeverityBadge severity={c.severity} />
                <span className="font-mono text-xs text-fg-secondary">
                  {c.path}
                  {c.line ? `:${c.line}` : ""}
                </span>
                <span className="text-fg-muted text-xs">{c.category}</span>
                {c.confidence != null && (
                  <span className="text-fg-muted text-xs">
                    conf {Math.round(c.confidence * 100)}%
                  </span>
                )}
              </div>
              <p className="mt-2 text-fg">{c.message}</p>
              {c.suggestion && (
                <pre className="mt-2 bg-bg border border-border-subtle rounded p-3 text-xs overflow-x-auto">
                  <code>{c.suggestion}</code>
                </pre>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-fg-muted uppercase tracking-wider">{label}</div>
      <div className="text-fg text-sm font-mono mt-1">{value}</div>
    </div>
  );
}

function SeverityBadge({ severity }) {
  const tone =
    {
      critical: "bg-danger/10 text-danger border-danger/30",
      major: "bg-warning/10 text-warning border-warning/30",
      minor: "bg-accent/10 text-accent border-accent/30",
      nit: "bg-surface text-fg-muted border-border-subtle",
    }[severity] || "bg-surface text-fg-muted border-border-subtle";
  return (
    <span className={`text-xs font-mono px-2 py-0.5 rounded border ${tone}`}>
      {severity}
    </span>
  );
}
