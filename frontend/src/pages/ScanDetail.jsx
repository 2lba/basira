import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { ArrowLeft, ExternalLink, Download, RefreshCw } from "lucide-react";
import { getScan, startScan } from "../api/client.js";
import { ScoreCircle, SeverityBadge } from "../components/features/ScanCard.jsx";
import { downloadMarkdown } from "../lib/scanMarkdown.js";

const ACTIVE = new Set(["pending", "running"]);

export default function ScanDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [scan, setScan] = useState(null);
  const [err, setErr] = useState(null);
  const [rescanning, setRescanning] = useState(false);
  const tick = useRef(0);

  useEffect(() => {
    let cancelled = false;
    tick.current += 1;
    const myTick = tick.current;

    async function load() {
      try {
        const s = await getScan(id);
        if (cancelled || myTick !== tick.current) return;
        setScan(s);
        if (ACTIVE.has(s.status)) {
          setTimeout(load, 1200);
        }
      } catch (e) {
        if (!cancelled) setErr(e.message);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (err) return <p className="text-danger">{err}</p>;
  if (!scan) return <p className="text-fg-muted">loading...</p>;

  const isActive = ACTIVE.has(scan.status);
  const groups = groupBySeverity(scan.findings || []);
  const ghBase = scan.repo_full_name
    ? `https://github.com/${scan.repo_full_name}`
    : null;

  async function onRescan() {
    setRescanning(true);
    try {
      const s = await startScan(scan.repository_id);
      navigate(`/scans/${s.id}`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setRescanning(false);
    }
  }

  function onExport() {
    downloadMarkdown(scan);
  }

  return (
    <section data-testid="scan-detail">
      <Link to={`/repos/${scan.repository_id}`} className="btn btn-ghost mb-4">
        <ArrowLeft size={14} />
        <span>back to repository</span>
      </Link>

      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">scan report</h1>
          <p className="mt-1 text-fg-secondary text-sm font-mono">
            {scan.repo_full_name}
            {scan.head_sha ? ` · ${scan.head_sha.slice(0, 7)}` : ""}
            {scan.ref ? ` · ${scan.ref}` : ""}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap" data-testid="scan-actions">
          <button
            data-testid="rescan-button"
            disabled={rescanning || isActive}
            onClick={onRescan}
            className="btn btn-ghost disabled:opacity-50"
          >
            <RefreshCw size={14} />
            <span>{rescanning ? "starting..." : "rescan now"}</span>
          </button>
          <button
            data-testid="export-md-button"
            disabled={isActive}
            onClick={onExport}
            className="btn btn-ghost disabled:opacity-50"
          >
            <Download size={14} />
            <span>export .md</span>
          </button>
        </div>
      </div>

      {isActive ? (
        <ProgressPanel scan={scan} />
      ) : (
        <ReportPanel scan={scan} groups={groups} ghBase={ghBase} />
      )}
    </section>
  );
}

function ProgressPanel({ scan }) {
  return (
    <div className="mt-6 card" data-testid="scan-progress">
      <h2 className="text-sm uppercase tracking-wider text-fg-muted">scanning</h2>
      <p className="mt-2 text-fg" data-testid="progress-message">
        {scan.progress_message || "queued"}
      </p>
      <div className="mt-4 w-full h-2 bg-bg border border-border-subtle rounded-full overflow-hidden">
        <div
          data-testid="progress-bar"
          className="h-full bg-accent transition-all"
          style={{ width: `${scan.progress}%` }}
          role="progressbar"
          aria-valuenow={scan.progress}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
      <p className="mt-2 text-fg-muted text-xs font-mono">{scan.progress}%</p>
    </div>
  );
}

function ReportPanel({ scan, groups, ghBase }) {
  if (scan.status === "failed") {
    return (
      <div className="mt-6 card border-danger/40">
        <h2 className="text-sm uppercase tracking-wider text-danger">scan failed</h2>
        <p className="mt-2 text-fg-secondary text-sm font-mono">
          {scan.error || "unknown error"}
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="mt-6 card flex items-start gap-6">
        <ScoreCircle score={scan.score} />
        <div className="flex-1">
          <h2 className="text-sm uppercase tracking-wider text-fg-muted">summary</h2>
          <p className="mt-2 text-fg leading-relaxed" data-testid="scan-summary">
            {scan.summary || "—"}
          </p>
          <dl className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <Stat label="status" value={scan.status} />
            <Stat label="files" value={scan.files_scanned ?? "—"} />
            <Stat label="model" value={scan.model || "—"} />
            <Stat
              label="cost"
              value={scan.cost_usd != null ? `$${scan.cost_usd.toFixed(4)}` : "—"}
            />
          </dl>
        </div>
      </div>

      <SeverityChips counts={scan.counts} />

      <h2 className="mt-8 text-sm uppercase tracking-wider text-fg-muted">
        findings ({(scan.findings || []).length})
      </h2>
      {(scan.findings || []).length === 0 ? (
        <p className="mt-4 text-fg-secondary">No issues found.</p>
      ) : (
        <div className="mt-4 space-y-6">
          {["critical", "major", "minor", "nit"].map((sev) =>
            groups[sev] && groups[sev].length > 0 ? (
              <SeverityGroup
                key={sev}
                severity={sev}
                items={groups[sev]}
                ghBase={ghBase}
                headSha={scan.head_sha}
              />
            ) : null,
          )}
        </div>
      )}
    </>
  );
}

function SeverityGroup({ severity, items, ghBase, headSha }) {
  return (
    <div data-testid={`severity-group-${severity}`}>
      <h3 className="text-xs uppercase tracking-wider text-fg-muted mb-2">
        {severity} ({items.length})
      </h3>
      <ul className="space-y-3">
        {items.map((f) => (
          <FindingItem key={f.id} finding={f} ghBase={ghBase} headSha={headSha} />
        ))}
      </ul>
    </div>
  );
}

function FindingItem({ finding, ghBase, headSha }) {
  const [open, setOpen] = useState(false);
  const ghUrl = buildGithubUrl(ghBase, headSha, finding.path, finding.line);
  return (
    <li className="card" data-testid="finding-item">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left"
        aria-expanded={open}
      >
        <div className="flex items-center gap-3 flex-wrap">
          <SeverityBadge severity={finding.severity} />
          <span className="font-mono text-xs text-fg-secondary">
            {finding.path}
            {finding.line ? `:${finding.line}` : ""}
          </span>
          <span className="text-fg-muted text-xs">{finding.category}</span>
          {finding.confidence != null && (
            <span className="text-fg-muted text-xs">
              conf {Math.round(finding.confidence * 100)}%
            </span>
          )}
        </div>
        <p className="mt-2 text-fg" data-testid="finding-message">
          {finding.message}
        </p>
      </button>
      {open && (
        <div className="mt-3 space-y-3" data-testid="finding-details">
          {finding.suggestion && (
            <pre className="bg-bg border border-border-subtle rounded p-3 text-xs overflow-x-auto">
              <code>{finding.suggestion}</code>
            </pre>
          )}
          {ghUrl && (
            <a
              href={ghUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
              data-testid="github-link"
            >
              <ExternalLink size={12} />
              view on github
            </a>
          )}
        </div>
      )}
    </li>
  );
}

function buildGithubUrl(base, sha, path, line) {
  if (!base || !path) return null;
  const ref = sha || "HEAD";
  return `${base}/blob/${ref}/${path}${line ? `#L${line}` : ""}`;
}

function groupBySeverity(findings) {
  return findings.reduce(
    (acc, f) => {
      (acc[f.severity] = acc[f.severity] || []).push(f);
      return acc;
    },
    { critical: [], major: [], minor: [], nit: [] },
  );
}

function SeverityChips({ counts }) {
  if (!counts) return null;
  return (
    <div className="mt-6 flex gap-2 flex-wrap" data-testid="severity-chips">
      <Chip label="critical" value={counts.critical || 0} tone="danger" />
      <Chip label="major" value={counts.major || 0} tone="warning" />
      <Chip label="minor" value={counts.minor || 0} tone="accent" />
      <Chip label="nit" value={counts.nit || 0} tone="muted" />
    </div>
  );
}

function Chip({ label, value, tone }) {
  const cls =
    {
      danger: "border-danger/30 text-danger",
      warning: "border-warning/30 text-warning",
      accent: "border-accent/30 text-accent",
      muted: "border-border-subtle text-fg-muted",
    }[tone] || "border-border-subtle text-fg-muted";
  return (
    <span
      className={`text-xs font-mono px-3 py-1 rounded border bg-surface ${cls}`}
      data-testid={`chip-${label}`}
    >
      {value} {label}
    </span>
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
