import { useEffect, useState } from "react";

export default function ChatWebhookCard({
  testId,
  title,
  description,
  load,
  save,
}) {
  const [state, setState] = useState(null);
  const [draft, setDraft] = useState({ url: "", enabled: false });
  const [error, setError] = useState(null);
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    load()
      .then((s) => {
        if (cancelled) return;
        setState(s);
        setDraft({ url: "", enabled: s.enabled });
      })
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [load]);

  if (!state) return <div className="mt-6 card h-32 animate-pulse" />;

  async function persist(extra = {}) {
    setSaving(true);
    setError(null);
    setStatus(null);
    try {
      const body = { ...extra };
      if (draft.url) body.url = draft.url;
      if (extra.enabled === undefined) body.enabled = draft.enabled;
      const updated = await save(body);
      setState(updated);
      setDraft({ url: "", enabled: updated.enabled });
      setStatus("saved");
      setTimeout(() => setStatus(null), 1500);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function clear() {
    setSaving(true);
    setError(null);
    try {
      const updated = await save({ clear: true });
      setState(updated);
      setDraft({ url: "", enabled: false });
      setStatus("cleared");
      setTimeout(() => setStatus(null), 1500);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const canEnable = state.url_set || !!draft.url;

  return (
    <div className="mt-6 card space-y-3" data-testid={testId}>
      <div>
        <h2 className="text-sm uppercase tracking-wider text-fg-muted">{title}</h2>
        <p className="mt-1 text-fg-secondary text-sm">{description}</p>
      </div>

      <label className="block text-sm">
        <span className="text-fg-muted text-xs uppercase tracking-wider">
          {state.url_set ? "replace webhook url" : "webhook url"}
        </span>
        <input
          data-testid={`${testId}-url`}
          className="input mt-1 font-mono text-xs"
          placeholder={state.url_set ? "stored — paste to replace" : "https://..."}
          value={draft.url}
          onChange={(e) => setDraft({ ...draft, url: e.target.value })}
        />
        {state.url_set && (
          <p className="text-fg-muted text-xs mt-1" data-testid={`${testId}-stored`}>
            webhook url is set
          </p>
        )}
      </label>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          data-testid={`${testId}-enabled`}
          disabled={!canEnable}
          className="w-4 h-4 accent-accent disabled:opacity-40"
          checked={!!draft.enabled}
          onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
        />
        <span>
          notify on scan finish
          {!canEnable && (
            <span className="text-fg-muted text-xs ml-1">
              (paste webhook url first)
            </span>
          )}
        </span>
      </label>

      {error && (
        <p className="text-danger text-sm" data-testid={`${testId}-error`}>
          {error}
        </p>
      )}
      {status && (
        <p className="text-success text-sm" data-testid={`${testId}-status`}>
          {status}
        </p>
      )}

      <div className="flex gap-2">
        <button
          data-testid={`${testId}-save`}
          disabled={saving}
          onClick={() => persist()}
          className="btn btn-primary disabled:opacity-50"
        >
          {saving ? "saving..." : "save"}
        </button>
        {state.url_set && (
          <button
            data-testid={`${testId}-clear`}
            disabled={saving}
            onClick={clear}
            className="btn btn-ghost text-danger disabled:opacity-40"
          >
            remove
          </button>
        )}
      </div>
    </div>
  );
}
