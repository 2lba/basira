import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { getRepo, updateRepo } from "../api/client.js";

const SEVERITIES = ["nit", "minor", "major", "critical"];
const MODELS = ["", "claude-sonnet-4-5", "claude-opus-4-5", "claude-haiku-4-5"];

export default function RepoDetail() {
  const { id } = useParams();
  const [repo, setRepo] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState(null);

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

  return (
    <section>
      <Link to="/" className="btn btn-ghost mb-4">
        <ArrowLeft size={14} />
        <span>back</span>
      </Link>

      <h1 className="text-2xl font-semibold tracking-tight">{repo.full_name}</h1>
      <p className="mt-1 text-fg-secondary text-sm">
        default branch: <span className="font-mono">{repo.default_branch}</span> ·
        {repo.private ? " private" : " public"}
      </p>

      <div className="mt-8 space-y-6 max-w-2xl">
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
