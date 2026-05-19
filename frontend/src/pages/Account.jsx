import { useEffect, useState } from "react";
import { getSmtp, updateSmtp } from "../api/client.js";

export default function Account({ user }) {
  return (
    <section className="max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight">account</h1>

      <div className="mt-6 card">
        <h2 className="text-sm uppercase tracking-wider text-fg-muted">profile</h2>
        <dl className="mt-3 space-y-3 text-sm">
          <Row label="github user">{user.github_login}</Row>
          <Row label="email">{user.email || "—"}</Row>
          <Row label="reviewly id" mono>{user.id}</Row>
        </dl>
      </div>

      <NotificationsCard />

      <div className="mt-6 card">
        <h2 className="text-sm uppercase tracking-wider text-fg-muted">
          install on more repos
        </h2>
        <p className="mt-2 text-fg-secondary text-sm">
          Use the GitHub App page to grant access to more repositories.
        </p>
      </div>
    </section>
  );
}

function NotificationsCard() {
  const [state, setState] = useState(null);
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getSmtp()
      .then((s) => {
        if (cancelled) return;
        setState(s);
        setDraft({
          smtp_host: s.smtp_host || "",
          smtp_port: s.smtp_port ?? "",
          smtp_username: s.smtp_username || "",
          smtp_from: s.smtp_from || "",
          smtp_use_tls: s.smtp_use_tls,
          notify_email_enabled: s.notify_email_enabled,
          smtp_password: "",
          clear_password: false,
        });
      })
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error && !state) return <p className="mt-6 text-danger">{error}</p>;
  if (!state || !draft)
    return <div className="mt-6 card h-40 animate-pulse" />;

  async function save() {
    setSaving(true);
    setError(null);
    setStatus(null);
    try {
      const body = {
        smtp_host: draft.smtp_host || null,
        smtp_port: draft.smtp_port === "" ? null : Number(draft.smtp_port),
        smtp_username: draft.smtp_username || null,
        smtp_from: draft.smtp_from || null,
        smtp_use_tls: !!draft.smtp_use_tls,
        notify_email_enabled: !!draft.notify_email_enabled,
        clear_password: !!draft.clear_password,
      };
      if (draft.smtp_password) body.smtp_password = draft.smtp_password;
      const updated = await updateSmtp(body);
      setState(updated);
      setDraft({
        smtp_host: updated.smtp_host || "",
        smtp_port: updated.smtp_port ?? "",
        smtp_username: updated.smtp_username || "",
        smtp_from: updated.smtp_from || "",
        smtp_use_tls: updated.smtp_use_tls,
        notify_email_enabled: updated.notify_email_enabled,
        smtp_password: "",
        clear_password: false,
      });
      setStatus("saved");
      setTimeout(() => setStatus(null), 1500);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const canEnable = !!(
    draft.smtp_host &&
    draft.smtp_port &&
    draft.smtp_from
  );

  return (
    <div className="mt-6 card space-y-4" data-testid="smtp-card">
      <div>
        <h2 className="text-sm uppercase tracking-wider text-fg-muted">
          email notifications
        </h2>
        <p className="mt-1 text-fg-secondary text-sm">
          Send yourself an email when a scan finishes. SMTP credentials stay on
          your own server; passwords are encrypted at rest.
        </p>
      </div>

      <Field label="SMTP host">
        <input
          data-testid="smtp-host"
          className="input"
          placeholder="smtp.example.com"
          value={draft.smtp_host}
          onChange={(e) => setDraft({ ...draft, smtp_host: e.target.value })}
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="port">
          <input
            data-testid="smtp-port"
            className="input"
            type="number"
            placeholder="587"
            value={draft.smtp_port}
            onChange={(e) => setDraft({ ...draft, smtp_port: e.target.value })}
          />
        </Field>
        <Field label="from address">
          <input
            data-testid="smtp-from"
            className="input"
            type="email"
            placeholder="alerts@example.com"
            value={draft.smtp_from}
            onChange={(e) => setDraft({ ...draft, smtp_from: e.target.value })}
          />
        </Field>
      </div>
      <Field label="username">
        <input
          data-testid="smtp-username"
          className="input"
          value={draft.smtp_username}
          onChange={(e) => setDraft({ ...draft, smtp_username: e.target.value })}
        />
      </Field>
      <Field
        label={
          state.password_set
            ? "password (leave blank to keep current)"
            : "password"
        }
      >
        <input
          data-testid="smtp-password"
          className="input"
          type="password"
          autoComplete="new-password"
          value={draft.smtp_password}
          onChange={(e) =>
            setDraft({ ...draft, smtp_password: e.target.value })
          }
        />
      </Field>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          data-testid="smtp-tls"
          className="w-4 h-4 accent-accent"
          checked={!!draft.smtp_use_tls}
          onChange={(e) =>
            setDraft({ ...draft, smtp_use_tls: e.target.checked })
          }
        />
        <span>use STARTTLS (recommended for port 587)</span>
      </label>

      <label
        className="flex items-center gap-2 text-sm"
        data-testid="notify-enabled-row"
      >
        <input
          type="checkbox"
          data-testid="notify-enabled"
          className="w-4 h-4 accent-accent disabled:opacity-40"
          checked={!!draft.notify_email_enabled}
          disabled={!canEnable}
          onChange={(e) =>
            setDraft({ ...draft, notify_email_enabled: e.target.checked })
          }
        />
        <span>
          email me when scans finish{" "}
          {!canEnable && (
            <span className="text-fg-muted text-xs">
              (fill host, port, from first)
            </span>
          )}
        </span>
      </label>

      {error && <p className="text-danger text-sm" data-testid="smtp-error">{error}</p>}
      {status && (
        <p className="text-success text-sm" data-testid="smtp-status">
          {status}
        </p>
      )}

      <div>
        <button
          data-testid="smtp-save"
          disabled={saving}
          onClick={save}
          className="btn btn-primary disabled:opacity-50"
        >
          {saving ? "saving..." : "save"}
        </button>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block text-sm">
      <span className="text-fg-muted text-xs uppercase tracking-wider">
        {label}
      </span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function Row({ label, children, mono }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-fg-muted">{label}</dt>
      <dd className={mono ? "font-mono text-xs" : ""}>{children}</dd>
    </div>
  );
}
