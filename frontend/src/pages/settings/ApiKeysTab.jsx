import { useEffect, useState } from "react";
import { Key, ExternalLink, Trash2, Check, RotateCw } from "lucide-react";
import {
  listApiKeys,
  putAnthropicKey,
  deleteAnthropicKey,
  testAnthropicKey,
} from "../../api/client.js";

export default function ApiKeysTab() {
  const [keys, setKeys] = useState(null);
  const [error, setError] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [busy, setBusy] = useState(null); // 'test' | 'remove' | null

  async function reload() {
    try {
      const data = await listApiKeys();
      setKeys(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  const anthropic = (keys || []).find((k) => k.provider === "anthropic");

  async function onTest() {
    setBusy("test");
    setError(null);
    try {
      const r = await testAnthropicKey();
      if (!r.valid) setError(r.error || "key is no longer valid");
      await reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function onRemove() {
    if (!confirm("Remove your Anthropic key? Scans will stop working until you add one.")) {
      return;
    }
    setBusy("remove");
    setError(null);
    try {
      await deleteAnthropicKey();
      await reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="max-w-2xl" data-testid="api-keys-tab">
      <div className="card space-y-4" data-testid="anthropic-key-card">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded bg-bg border border-border-subtle">
            <Key size={16} className="text-fg-muted" />
          </div>
          <div className="flex-1">
            <h2 className="text-base font-medium text-fg">Anthropic (Claude)</h2>
            <p className="text-fg-secondary text-sm mt-1">
              Your key powers every scan you run. We store it Fernet-encrypted
              at rest and never show the plain value back to you.
            </p>
          </div>
        </div>

        {keys === null ? (
          <div className="card h-12 animate-pulse" />
        ) : anthropic ? (
          <ConfiguredState
            row={anthropic}
            onUpdate={() => setModalOpen(true)}
            onTest={onTest}
            onRemove={onRemove}
            busy={busy}
          />
        ) : (
          <EmptyState onAdd={() => setModalOpen(true)} />
        )}

        {error && (
          <p className="text-danger text-sm" data-testid="api-key-error">
            {error}
          </p>
        )}
      </div>

      {modalOpen && (
        <AddKeyModal
          onClose={() => setModalOpen(false)}
          onSaved={async () => {
            setModalOpen(false);
            await reload();
          }}
        />
      )}
    </div>
  );
}

function ConfiguredState({ row, onUpdate, onTest, onRemove, busy }) {
  return (
    <div className="space-y-3" data-testid="anthropic-key-configured">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="font-mono text-sm text-fg-secondary">
          sk-ant-···· {row.key_last_four}
        </span>
        {row.is_valid ? (
          <span
            data-testid="key-status-valid"
            className="inline-flex items-center gap-1 text-xs font-mono px-2 py-0.5 rounded border border-success/30 bg-success/10 text-success"
          >
            <Check size={12} /> valid
          </span>
        ) : (
          <span
            data-testid="key-status-invalid"
            className="text-xs font-mono px-2 py-0.5 rounded border border-danger/30 bg-danger/10 text-danger"
          >
            invalid — re-test or replace
          </span>
        )}
      </div>
      {row.last_validated_at && (
        <p className="text-xs text-fg-muted">
          last verified {new Date(row.last_validated_at).toLocaleString()}
        </p>
      )}
      <div className="flex gap-2 flex-wrap">
        <button
          data-testid="update-key-btn"
          onClick={onUpdate}
          className="btn btn-primary"
        >
          update key
        </button>
        <button
          data-testid="test-key-btn"
          onClick={onTest}
          disabled={busy === "test"}
          className="btn btn-ghost disabled:opacity-50"
        >
          <RotateCw size={14} />
          <span>{busy === "test" ? "testing..." : "test"}</span>
        </button>
        <button
          data-testid="remove-key-btn"
          onClick={onRemove}
          disabled={busy === "remove"}
          className="btn btn-ghost text-danger disabled:opacity-50"
        >
          <Trash2 size={14} />
          <span>{busy === "remove" ? "removing..." : "remove"}</span>
        </button>
      </div>
    </div>
  );
}

function EmptyState({ onAdd }) {
  return (
    <div
      className="rounded border border-dashed border-border-subtle p-4 text-center"
      data-testid="anthropic-key-empty"
    >
      <p className="text-fg-secondary text-sm">
        Add your Anthropic API key to start scanning.
      </p>
      <button
        data-testid="add-key-btn"
        onClick={onAdd}
        className="btn btn-primary mt-3"
      >
        add anthropic key
      </button>
    </div>
  );
}

function AddKeyModal({ onClose, onSaved }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await putAnthropicKey(value.trim());
      await onSaved();
    } catch (e) {
      // expose the backend's INVALID_API_KEY message verbatim — it's
      // already user-readable ("anthropic rejected this key", etc.)
      setError(e.message || "could not save key");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      data-testid="add-key-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="card max-w-lg w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-medium">add anthropic api key</h3>
        <p className="mt-2 text-fg-secondary text-sm">
          Get a key from{" "}
          <a
            className="text-accent hover:underline inline-flex items-center gap-1"
            href="https://console.anthropic.com/settings/keys"
            target="_blank"
            rel="noreferrer noopener"
          >
            console.anthropic.com/settings/keys
            <ExternalLink size={11} />
          </a>
          . Keys starting with <code className="font-mono">sk-ant-</code>.
        </p>
        <label className="block mt-4 text-sm">
          <span className="text-fg-muted text-xs uppercase tracking-wider">
            api key
          </span>
          <input
            data-testid="api-key-input"
            type="password"
            autoComplete="off"
            spellCheck="false"
            placeholder="sk-ant-..."
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="input mt-1 font-mono text-sm"
          />
        </label>

        {error && (
          <p
            data-testid="add-key-error"
            className="mt-3 text-danger text-sm"
          >
            {error}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="btn btn-ghost">
            cancel
          </button>
          <button
            data-testid="save-key-btn"
            onClick={save}
            disabled={saving || value.trim().length < 20}
            className="btn btn-primary disabled:opacity-50"
          >
            {saving ? "validating..." : "save"}
          </button>
        </div>
      </div>
    </div>
  );
}
