import { Link } from "react-router-dom";

export function ScoreCircle({ score, size = 96 }) {
  const s = typeof score === "number" ? score : null;
  const tone = s == null
    ? "text-fg-muted"
    : s >= 80
      ? "text-success"
      : s >= 60
        ? "text-warning"
        : "text-danger";
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const offset = s == null ? circ : circ - (s / 100) * circ;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="rotate-[-90deg]">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="currentColor"
          strokeWidth="4"
          fill="none"
          className="text-border-subtle"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="currentColor"
          strokeWidth="4"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          className={tone}
          style={{ transition: "stroke-dashoffset 200ms ease-out" }}
        />
      </svg>
      <div className={`absolute inset-0 flex items-center justify-center ${tone}`}>
        <span className="text-xl font-semibold">{s == null ? "—" : s}</span>
      </div>
    </div>
  );
}

export function SeverityBadge({ severity }) {
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

export function ScanListRow({ scan }) {
  return (
    <Link
      to={`/scans/${scan.id}`}
      className="card flex items-center justify-between hover:border-border transition-colors"
    >
      <div className="flex items-center gap-4">
        <ScoreCircle score={scan.score} size={56} />
        <div>
          <div className="text-fg font-medium">
            scan {scan.head_sha ? scan.head_sha.slice(0, 7) : "queued"}
          </div>
          <div className="text-fg-muted text-xs mt-0.5">
            {scan.summary || scan.progress_message || scan.status}
          </div>
          <div className="text-fg-muted text-xs mt-1 font-mono">
            {new Date(scan.created_at).toLocaleString()}
            {scan.ref ? ` · ${scan.ref}` : ""}
          </div>
        </div>
      </div>
      <CountsInline counts={scan.counts} status={scan.status} error={scan.error} />
    </Link>
  );
}

export function CountsInline({ counts, status, error }) {
  if (status === "running" || status === "pending") {
    return <span className="text-fg-muted text-xs">in progress</span>;
  }
  if (status === "failed") {
    if ((error || "").includes("MISSING_API_KEY")) {
      return (
        <span
          data-testid="counts-missing-key"
          className="text-warning text-xs"
        >
          no api key
        </span>
      );
    }
    return <span className="text-danger text-xs">failed</span>;
  }
  if (!counts || !counts.total) {
    return <span className="text-success text-xs">clean</span>;
  }
  return (
    <span className="font-mono text-xs flex gap-2" data-testid="counts-inline">
      {counts.critical ? <span className="text-danger">{counts.critical} crit</span> : null}
      {counts.major ? <span className="text-warning">{counts.major} maj</span> : null}
      {counts.minor ? <span className="text-fg-secondary">{counts.minor} min</span> : null}
      {counts.nit ? <span className="text-fg-muted">{counts.nit} nit</span> : null}
    </span>
  );
}
