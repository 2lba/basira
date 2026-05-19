import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { ArrowLeft, Play, GitCompare } from "lucide-react";
import {
  getRepo,
  updateRepo,
  startScan,
  listRepoScans,
} from "../api/client.js";
import { ScanListRow } from "../components/features/ScanCard.jsx";

const SEVERITIES = ["nit", "minor", "major", "critical"];
const MODELS = ["", "claude-sonnet-4-5", "claude-opus-4-5", "claude-haiku-4-5"];
const ACTIVE = new Set(["pending", "running"]);

export default function RepoDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [repo, setRepo] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState(null);
  const [scans, setScans] = useState(null);
  const [scanError, setScanError] = useState(null);
  const [starting, setStarting] = useState(false);
  const [selected, setSelected] = useState([]);
  const pollRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    getRepo(id)
      .then((r) => {
        if (cancelled) return;
        setRepo(r);
        setDraft({
          review_enabled: r.review_enabled,
          severity_threshold: r.severity_threshold,
          ignored_paths: (r.ignored_paths || []).join("\n"),
          custom_rules: r.custom_rules || "",
          model_override: r.model_override || "",
        });
      })
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    pollRef.current += 1;
    const myTick = pollRef.current;

    async function load() {
      try {
        const list = await listRepoScans(id);
        if (cancelled || myTick !== pollRef.current) return;
        setScans(list);
        const anyActive = list.some((s) => ACTIVE.has(s.status));
        if (anyActive) {
          setTimeout(load, 1200);
        }
      } catch (e) {
        if (!cancelled) setScanError(e.message);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <p className="text-danger">{error}</p>;
  if (!repo || !draft) return <p className="text-fg-muted">loading...</p>;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const body = {
        review_enabled: draft.review_enabled,
        severity_threshold: draft.severity_threshold,
        ignored_paths: draft.ignored_paths
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        custom_rules: draft.custom_rules,
        model_override: draft.model_override,
      };
      const updated = await updateRepo(id, body);
      setRepo(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function scanNow() {
    setStarting(true);
    setScanError(null);
    try {
      const s = await startScan(id);
      setScans((prev) => {
        const filtered = (prev || []).filter((x) => x.id !== s.id);
        return [s, ...filtered];
      });
      // restart polling
      pollRef.current += 1;
      const myTick = pollRef.current;
      const poll = async () => {
        try {
          const list = await listRepoScans(id);
          if (myTick !== pollRef.current) return;
          setScans(list);
          if (list.some((x) => ACTIVE.has(x.status))) {
            setTimeout(poll, 1200);
          }
        } catch {
          // swallow during polling
        }
      };
      setTimeout(poll, 800);
    } catch (e) {
      setScanError(e.message);
    } finally {
      setStarting(false);
    }
  }

  const activeScan = (scans || []).find((s) => ACTIVE.has(s.status));
  const recentDone = (scans || []).filter((s) => !ACTIVE.has(s.status));

  function toggleSelect(scanId) {
    setSelected((prev) => {
      if (prev.includes(scanId)) return prev.filter((x) => x !== scanId);
      if (prev.length >= 2) return [prev[1], scanId];
      return [...prev, scanId];
    });
  }

  function compareNow() {
    if (selected.length !== 2) return;
    const [a, b] = selected;
    navigate(`/scans/compare?a=${a}&b=${b}`);
  }

  return (
    <section data-testid="repo-detail">
      <Link to="/" className="btn btn-ghost mb-4">
        <ArrowLeft size={14} />
        <span>back</span>
      </Link>

      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{repo.full_name}</h1>
          <p className="mt-1 text-fg-secondary text-sm">
            default branch:{" "}
            <span className="font-mono">{repo.default_branch}</span> ·
            {repo.private ? " private" : " public"}
          </p>
        </div>
        <button
          data-testid="scan-now"
          disabled={starting || !!activeScan}
          onClick={scanNow}
          className="btn btn-primary disabled:opacity-50"
        >
          <Play size={14} />
          <span>
            {activeScan ? "scanning..." : starting ? "starting..." : "scan now"}
          </span>
        </button>
      </div>

      <div className="mt-8 space-y-6" data-testid="scans-section">
        <div className="flex items-center justify-between">
          <h2 className="text-sm uppercase tracking-wider text-fg-muted">scans</h2>
          {recentDone.length >= 2 && (
            <button
              data-testid="compare-button"
              disabled={selected.length !== 2}
              onClick={compareNow}
              className="btn btn-ghost disabled:opacity-40"
            >
              <GitCompare size={14} />
              <span>
                {selected.length === 2
                  ? "compare selected"
                  : `compare (${selected.length}/2)`}
              </span>
            </button>
          )}
        </div>
        {scanError && <p className="text-danger text-sm">{scanError}</p>}
        {activeScan && (
          <ActiveScanCard scan={activeScan} />
        )}
        {scans === null ? (
          <div className="card h-20 animate-pulse" />
        ) : recentDone.length === 0 && !activeScan ? (
          <p className="text-fg-secondary text-sm">
            No scans yet. Click "scan now" to run your first repository scan.
          </p>
        ) : (
          <ul className="space-y-2" data-testid="scan-history">
            {recentDone.map((s) => (
              <li key={s.id} className="flex items-center gap-3">
                {recentDone.length >= 2 && (
                  <input
                    type="checkbox"
                    aria-label={`select scan ${s.id}`}
                    data-testid={`select-scan-${s.id}`}
                    checked={selected.includes(s.id)}
                    onChange={() => toggleSelect(s.id)}
                    className="w-4 h-4 accent-accent"
                  />
                )}
                <div className="flex-1">
                  <ScanListRow scan={s} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-12 space-y-6 max-w-2xl">
        <h2 className="text-sm uppercase tracking-wider text-fg-muted">settings</h2>

        <div className="card">
          <Label>review status</Label>
          <div className="mt-2 flex items-center gap-3">
            <Toggle
              checked={draft.review_enabled}
              onChange={(v) => setDraft({ ...draft, review_enabled: v })}
            />
            <span className="text-sm text-fg-secondary">
              {draft.review_enabled ? "enabled" : "paused"}
            </span>
          </div>
        </div>

        <div className="card">
          <Label>severity threshold</Label>
          <p className="text-fg-muted text-xs mt-1">
            Only findings at or above this severity are posted.
          </p>
          <select
            value={draft.severity_threshold}
            onChange={(e) =>
              setDraft({ ...draft, severity_threshold: e.target.value })
            }
            className="input mt-3"
          >
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="card">
          <Label>model override</Label>
          <p className="text-fg-muted text-xs mt-1">
            Leave blank to use the global default.
          </p>
          <select
            value={draft.model_override}
            onChange={(e) =>
              setDraft({ ...draft, model_override: e.target.value })
            }
            className="input mt-3"
          >
            {MODELS.map((m) => (
              <option key={m} value={m}>
                {m || "(default)"}
              </option>
            ))}
          </select>
        </div>

        <div className="card">
          <Label>ignored paths</Label>
          <p className="text-fg-muted text-xs mt-1">
            One regex per line. Files matching are skipped by review.
          </p>
          <textarea
            value={draft.ignored_paths}
            onChange={(e) => setDraft({ ...draft, ignored_paths: e.target.value })}
            rows={6}
            className="input mt-3 font-mono text-xs"
          />
        </div>

        <div className="card">
          <Label>custom rules</Label>
          <p className="text-fg-muted text-xs mt-1">
            Free-form instructions appended to the review prompt. Keep it short.
          </p>
          <textarea
            value={draft.custom_rules}
            onChange={(e) => setDraft({ ...draft, custom_rules: e.target.value })}
            rows={4}
            className="input mt-3"
          />
        </div>

        {error && <p className="text-danger text-sm">{error}</p>}

        <div className="flex gap-3">
          <button
            disabled={saving}
            onClick={save}
            className="btn btn-primary disabled:opacity-50"
          >
            {saving ? "saving..." : "save changes"}
          </button>
        </div>
      </div>
    </section>
  );
}

function ActiveScanCard({ scan }) {
  return (
    <Link
      to={`/scans/${scan.id}`}
      className="card block hover:border-border transition-colors"
      data-testid="active-scan-card"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex-1">
          <p className="text-fg text-sm" data-testid="active-progress-message">
            {scan.progress_message || "queued"}
          </p>
          <div className="mt-2 w-full h-1.5 bg-bg border border-border-subtle rounded-full overflow-hidden">
            <div
              data-testid="active-progress-bar"
              className="h-full bg-accent transition-all"
              style={{ width: `${scan.progress}%` }}
            />
          </div>
        </div>
        <span className="text-fg-muted text-xs font-mono">{scan.progress}%</span>
      </div>
    </Link>
  );
}

function Label({ children }) {
  return <label className="text-sm text-fg font-medium">{children}</label>;
}

function Toggle({ checked, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
        checked ? "bg-accent" : "bg-surface border border-border-subtle"
      }`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
          checked ? "translate-x-5" : "translate-x-1"
        }`}
      />
    </button>
  );
}
