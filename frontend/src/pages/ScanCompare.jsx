import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { compareScans } from "../api/client.js";
import { ScoreCircle, SeverityBadge } from "../components/features/ScanCard.jsx";

export default function ScanCompare() {
  const [params] = useSearchParams();
  const a = params.get("a");
  const b = params.get("b");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (!a || !b) {
      setError("missing scan ids");
      return;
    }
    compareScans(a, b)
      .then((r) => !cancelled && setResult(r))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [a, b]);

  if (error) return <p className="text-danger">{error}</p>;
  if (!result) return <p className="text-fg-muted">loading...</p>;

  const { a: scanA, b: scanB, score_delta, counts_delta } = result;
  const deltaTone =
    score_delta == null
      ? "text-fg-muted"
      : score_delta > 0
        ? "text-success"
        : score_delta < 0
          ? "text-danger"
          : "text-fg-muted";

  return (
    <section data-testid="scan-compare">
      <Link to={`/repos/${scanA.repository_id}`} className="btn btn-ghost mb-4">
        <ArrowLeft size={14} />
        <span>back to repository</span>
      </Link>

      <h1 className="text-2xl font-semibold tracking-tight">compare scans</h1>
      <p className="mt-1 text-fg-secondary text-sm font-mono">
        {scanA.repo_full_name}
      </p>

      <div className="mt-6 card flex items-center justify-around gap-4 flex-wrap">
        <ScanSummary scan={scanA} label="A (earlier)" />
        <div className="text-fg-muted">
          <ArrowRight size={20} />
        </div>
        <ScanSummary scan={scanB} label="B (later)" />
        <div className="border-l border-border-subtle pl-6">
          <div className="text-xs uppercase tracking-wider text-fg-muted">
            score Δ
          </div>
          <div className={`text-3xl font-semibold mt-1 ${deltaTone}`} data-testid="score-delta">
            {score_delta == null
              ? "—"
              : score_delta > 0
                ? `+${score_delta}`
                : `${score_delta}`}
          </div>
        </div>
      </div>

      <div
        className="mt-6 grid grid-cols-2 md:grid-cols-5 gap-3"
        data-testid="counts-delta"
      >
        {["total", "critical", "major", "minor", "nit"].map((k) => (
          <DeltaChip key={k} label={k} delta={counts_delta[k]} />
        ))}
      </div>

      <Section
        testId="resolved-section"
        title="resolved"
        tone="success"
        items={result.resolved_findings}
        emptyText="No findings were resolved."
      />
      <Section
        testId="new-section"
        title="new"
        tone="danger"
        items={result.new_findings}
        emptyText="No new findings."
      />
      <Section
        testId="persisting-section"
        title="persisting"
        tone="muted"
        items={result.persisting_findings}
        emptyText="No findings persisted."
      />
    </section>
  );
}

function ScanSummary({ scan, label }) {
  return (
    <div className="flex items-center gap-3" data-testid={`scan-summary-${label.includes("A") ? "a" : "b"}`}>
      <ScoreCircle score={scan.score} size={60} />
      <div>
        <div className="text-xs uppercase tracking-wider text-fg-muted">
          {label}
        </div>
        <div className="text-fg text-sm font-mono mt-0.5">
          {scan.head_sha ? scan.head_sha.slice(0, 7) : "—"}
        </div>
        <div className="text-fg-muted text-xs mt-0.5">
          {new Date(scan.created_at).toLocaleString()}
        </div>
      </div>
    </div>
  );
}

function DeltaChip({ label, delta }) {
  const tone =
    delta == null || delta === 0
      ? "text-fg-muted border-border-subtle"
      : delta > 0
        ? "text-danger border-danger/30"
        : "text-success border-success/30";
  const sign = delta == null ? "—" : delta > 0 ? `+${delta}` : `${delta}`;
  return (
    <div className={`card flex items-center justify-between border ${tone}`}>
      <span className="text-xs uppercase tracking-wider">{label}</span>
      <span className="font-mono text-sm" data-testid={`delta-${label}`}>
        {sign}
      </span>
    </div>
  );
}

function Section({ testId, title, tone, items, emptyText }) {
  const headerTone =
    {
      success: "text-success",
      danger: "text-danger",
      muted: "text-fg-muted",
    }[tone] || "text-fg-muted";
  return (
    <div className="mt-8" data-testid={testId}>
      <h2 className={`text-sm uppercase tracking-wider ${headerTone}`}>
        {title} ({items.length})
      </h2>
      {items.length === 0 ? (
        <p className="mt-3 text-fg-secondary text-sm">{emptyText}</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.map((f, i) => (
            <li key={`${f.path}:${f.line}:${i}`} className="card">
              <div className="flex items-center gap-3 flex-wrap">
                <SeverityBadge severity={f.severity} />
                <span className="font-mono text-xs text-fg-secondary">
                  {f.path}
                  {f.line ? `:${f.line}` : ""}
                </span>
                <span className="text-fg-muted text-xs">{f.category}</span>
              </div>
              <p className="mt-2 text-fg text-sm">{f.message}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
