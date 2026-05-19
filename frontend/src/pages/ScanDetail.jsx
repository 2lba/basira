import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  ExternalLink,
  Download,
  RefreshCw,
  Share2,
  X,
  CheckCircle2,
  Slash,
  EyeOff,
} from "lucide-react";
import {
  getScan,
  startScan,
  createShare,
  revokeShare,
  resolveFinding,
  markFalsePositive,
  ignoreFindingRule,
} from "../api/client.js";
import { ScoreCircle, SeverityBadge } from "../components/features/ScanCard.jsx";
import { downloadMarkdown } from "../lib/scanMarkdown.js";

const ACTIVE = new Set(["pending", "running"]);

export default function ScanDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [scan, setScan] = useState(null);
  const [err, setErr] = useState(null);
  const [rescanning, setRescanning] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [shareUrl, setShareUrl] = useState(null);
  const [shareBusy, setShareBusy] = useState(false);
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

  const [hiddenIds, setHiddenIds] = useState(() => new Set());
  const [hiddenCategories, setHiddenCategories] = useState(() => new Set());

  if (err) return <p className="text-danger">{err}</p>;
  if (!scan) return <p className="text-fg-muted">loading...</p>;

  const isActive = ACTIVE.has(scan.status);
  const visibleFindings = (scan.findings || []).filter((f) => {
    if (hiddenIds.has(f.id)) return false;
    if (hiddenCategories.has(f.category)) return false;
    return true;
  });
  const groups = groupBySeverity(visibleFindings);
  const ghBase = scan.repo_full_name
    ? `https://github.com/${scan.repo_full_name}`
    : null;

  function hideFinding(id) {
    setHiddenIds((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  }
  function hideCategory(category) {
    setHiddenCategories((prev) => {
      const next = new Set(prev);
      next.add(category);
      return next;
    });
  }

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

  async function onShare() {
    setShareOpen(true);
    if (shareUrl) return;
    setShareBusy(true);
    try {
      const res = await createShare(scan.id);
      setShareUrl(res.url);
    } catch (e) {
      setErr(e.message);
      setShareOpen(false);
    } finally {
      setShareBusy(false);
    }
  }

  async function onRevoke() {
    setShareBusy(true);
    try {
      await revokeShare(scan.id);
      setShareUrl(null);
      setShareOpen(false);
    } catch (e) {
      setErr(e.message);
    } finally {
      setShareBusy(false);
    }
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
          <button
            data-testid="share-button"
            disabled={isActive}
            onClick={onShare}
            className="btn btn-ghost disabled:opacity-50"
          >
            <Share2 size={14} />
            <span>share</span>
          </button>
        </div>
      </div>

      {shareOpen && (
        <ShareModal
          url={shareUrl}
          busy={shareBusy}
          onClose={() => setShareOpen(false)}
          onRevoke={onRevoke}
        />
      )}

      {isActive ? (
        <ProgressPanel scan={scan} />
      ) : (
        <ReportPanel
          scan={scan}
          groups={groups}
          visibleCount={visibleFindings.length}
          ghBase={ghBase}
          onHide={hideFinding}
          onHideCategory={hideCategory}
        />
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

function ReportPanel({ scan, groups, visibleCount, ghBase, onHide, onHideCategory }) {
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

      <FindingsList
        scan={scan}
        groups={groups}
        visibleCount={visibleCount}
        ghBase={ghBase}
        onHide={onHide}
        onHideCategory={onHideCategory}
      />
    </>
  );
}

function FindingsList({ scan, groups, visibleCount, ghBase, onHide, onHideCategory }) {
  const total = (scan.findings || []).length;
  const hidden = total - visibleCount;
  return (
    <>
      <h2 className="mt-8 text-sm uppercase tracking-wider text-fg-muted">
        findings ({visibleCount})
        {hidden > 0 && (
          <span className="ml-2 text-fg-muted normal-case" data-testid="hidden-count">
            ({hidden} hidden)
          </span>
        )}
      </h2>
      {visibleCount === 0 ? (
        <p className="mt-4 text-fg-secondary">
          {total === 0 ? "No issues found." : "All findings filtered out."}
        </p>
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
                onHide={onHide}
                onHideCategory={onHideCategory}
              />
            ) : null,
          )}
        </div>
      )}
    </>
  );
}

function SeverityGroup({ severity, items, ghBase, headSha, onHide, onHideCategory }) {
  return (
    <div data-testid={`severity-group-${severity}`}>
      <h3 className="text-xs uppercase tracking-wider text-fg-muted mb-2">
        {severity} ({items.length})
      </h3>
      <ul className="space-y-3">
        {items.map((f) => (
          <FindingItem
            key={f.id}
            finding={f}
            ghBase={ghBase}
            headSha={headSha}
            onHide={onHide}
            onHideCategory={onHideCategory}
          />
        ))}
      </ul>
    </div>
  );
}

function FindingItem({ finding, ghBase, headSha, onHide, onHideCategory }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(null);
  const [err, setErr] = useState(null);
  const ghUrl = buildGithubUrl(ghBase, headSha, finding.path, finding.line);

  async function act(kind, fn) {
    setBusy(kind);
    setErr(null);
    try {
      await fn(finding.id);
      if (kind === "ignore-rule") {
        onHideCategory(finding.category);
      } else {
        onHide(finding.id);
      }
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  }

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
          <div className="flex gap-2 flex-wrap pt-2 border-t border-border-subtle" data-testid="finding-actions">
            <ActionBtn
              testId="action-resolve"
              icon={<CheckCircle2 size={12} />}
              label="mark resolved"
              busy={busy === "resolve"}
              onClick={() => act("resolve", resolveFinding)}
            />
            <ActionBtn
              testId="action-false-positive"
              icon={<Slash size={12} />}
              label="false positive"
              busy={busy === "false-positive"}
              onClick={() => act("false-positive", markFalsePositive)}
            />
            <ActionBtn
              testId="action-ignore-rule"
              icon={<EyeOff size={12} />}
              label={`ignore "${finding.category}"`}
              busy={busy === "ignore-rule"}
              onClick={() => act("ignore-rule", ignoreFindingRule)}
            />
          </div>
          {err && <p className="text-danger text-xs" data-testid="action-error">{err}</p>}
        </div>
      )}
    </li>
  );
}

function ActionBtn({ testId, icon, label, busy, onClick }) {
  return (
    <button
      type="button"
      data-testid={testId}
      disabled={busy}
      onClick={onClick}
      className="inline-flex items-center gap-1 text-xs text-fg-secondary hover:text-fg border border-border-subtle hover:border-border rounded px-2 py-1 disabled:opacity-50 transition-colors"
    >
      {icon}
      <span>{busy ? "..." : label}</span>
    </button>
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

function ShareModal({ url, busy, onClose, onRevoke }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      // clipboard may be blocked; fall back silently
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      data-testid="share-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="card max-w-lg w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-lg font-medium">share this scan</h3>
          <button
            type="button"
            aria-label="close"
            onClick={onClose}
            className="text-fg-muted hover:text-fg"
          >
            <X size={16} />
          </button>
        </div>
        <p className="mt-2 text-fg-secondary text-sm">
          Anyone with this link can view the report, even without an account.
        </p>
        <div className="mt-4">
          {busy && !url ? (
            <div className="card h-10 animate-pulse" />
          ) : url ? (
            <div className="flex gap-2">
              <input
                data-testid="share-url-input"
                readOnly
                value={url}
                onFocus={(e) => e.target.select()}
                className="input flex-1 font-mono text-xs"
              />
              <button
                data-testid="share-copy-button"
                onClick={copy}
                className="btn btn-primary"
              >
                {copied ? "copied" : "copy"}
              </button>
            </div>
          ) : null}
        </div>
        <div className="mt-4 flex justify-end">
          <button
            data-testid="share-revoke-button"
            disabled={busy || !url}
            onClick={onRevoke}
            className="btn btn-ghost text-danger disabled:opacity-40"
          >
            revoke link
          </button>
        </div>
      </div>
    </div>
  );
}
