import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import {
  getSmtp,
  updateSmtp,
  getSlack,
  updateSlack,
  getDiscord,
  updateDiscord,
} from "../../api/client.js";
import ChatWebhookCard from "../../components/features/ChatWebhookCard.jsx";

export default function NotificationsTab() {
  return (
    <div className="max-w-2xl" data-testid="notifications-tab">
      <SmtpCard />
      <ChatWebhookCard
        testId="slack-card"
        title="slack"
        description="Post scan results to a Slack channel via an incoming webhook."
        load={getSlack}
        save={updateSlack}
      />
      <ChatWebhookCard
        testId="discord-card"
        title="discord"
        description="Post scan results to a Discord channel via a webhook URL."
        load={getDiscord}
        save={updateDiscord}
      />
    </div>
  );
}

function SmtpCard() {
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
        setDraft(toDraft(s));
      })
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error && !state) return <p className="text-danger">{error}</p>;
  if (!state || !draft) return <div className="card h-40 animate-pulse" />;

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
      setDraft(toDraft(updated));
      setStatus("saved");
      setTimeout(() => setStatus(null), 1500);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const canEnable = !!(draft.smtp_host && draft.smtp_port && draft.smtp_from);

  return (
    <div className="card space-y-4" data-testid="smtp-card">
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <h2 className="text-sm uppercase tracking-wider text-fg-muted">
            email notifications
          </h2>
          <span
            data-testid="smtp-optional-badge"
            className="text-xs px-2 py-0.5 rounded border border-border-subtle text-fg-muted"
          >
            Optional · Requires your own SMTP
          </span>
        </div>
        <p className="mt-2 text-fg-secondary text-sm">
          Send yourself an email when a scan finishes. SMTP credentials stay on
          your own server; passwords are encrypted at rest.
        </p>
        <p
          className="mt-2 text-fg-muted text-xs"
          data-testid="smtp-alternatives-hint"
        >
          Don't have SMTP? Use Slack or Discord below instead — they work with
          just a webhook URL.
        </p>
        <SmtpGuide />
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
            <span
              className="text-fg-muted text-xs"
              data-testid="smtp-disabled-hint"
            >
              Configure SMTP first to enable email.
            </span>
          )}
        </span>
      </label>

      {error && (
        <p className="text-danger text-sm" data-testid="smtp-error">
          {error}
        </p>
      )}
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

function SmtpGuide() {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-3" data-testid="smtp-guide">
      <button
        type="button"
        data-testid="smtp-guide-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <span>{open ? "hide" : "how to set this up"}</span>
      </button>
      {open && (
        <div
          className="mt-3 bg-bg border border-border-subtle rounded p-3 text-xs text-fg-secondary space-y-3"
          data-testid="smtp-guide-body"
        >
          <p>
            SMTP is the protocol your email provider uses to send mail. You
            need 4 things to enable email alerts:
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              <span className="text-fg">host</span> — the server name (e.g.
              smtp.gmail.com)
            </li>
            <li>
              <span className="text-fg">port</span> — usually 587 (with
              STARTTLS) or 465 (with SSL)
            </li>
            <li>
              <span className="text-fg">username</span> — your email or API key
              identity
            </li>
            <li>
              <span className="text-fg">password</span> — an app password or
              API key; not your account password
            </li>
          </ul>

          <div>
            <p className="text-fg">Example: Gmail</p>
            <p className="mt-1">
              host <code className="font-mono">smtp.gmail.com</code>, port{" "}
              <code className="font-mono">587</code>, STARTTLS on, username
              your gmail address, password an{" "}
              <a
                href="https://myaccount.google.com/apppasswords"
                target="_blank"
                rel="noreferrer noopener"
                className="text-accent hover:underline"
              >
                App Password
              </a>{" "}
              (not your account password). 2FA must be on.
            </p>
          </div>

          <div>
            <p className="text-fg">Example: Resend (free SMTP)</p>
            <p className="mt-1">
              Sign up at{" "}
              <a
                href="https://resend.com"
                target="_blank"
                rel="noreferrer noopener"
                className="text-accent hover:underline"
              >
                resend.com
              </a>
              , create an API key. Then use host{" "}
              <code className="font-mono">smtp.resend.com</code>, port{" "}
              <code className="font-mono">587</code>, username{" "}
              <code className="font-mono">resend</code>, password = your API
              key. Free tier covers 3000 emails/month.
            </p>
          </div>

          <p className="text-fg-muted">
            Prefer not to configure SMTP at all? Slack and Discord work with
            just a webhook URL — no credentials needed.
          </p>
        </div>
      )}
    </div>
  );
}

function toDraft(s) {
  return {
    smtp_host: s.smtp_host || "",
    smtp_port: s.smtp_port ?? "",
    smtp_username: s.smtp_username || "",
    smtp_from: s.smtp_from || "",
    smtp_use_tls: s.smtp_use_tls,
    notify_email_enabled: s.notify_email_enabled,
    smtp_password: "",
    clear_password: false,
  };
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
