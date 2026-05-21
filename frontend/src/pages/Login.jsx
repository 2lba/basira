import { useEffect, useState } from "react";
import { Github, AlertTriangle } from "lucide-react";
import { githubLoginUrl } from "../api/client.js";
import Logo from "../components/Logo.jsx";

// Map backend OAuth error codes to readable copy. Keep concrete failures
// distinct so support has a fighting chance.
const OAUTH_MESSAGES = {
  OAUTH_DENIED: "You declined the GitHub authorization.",
  OAUTH_BAD_REQUEST: "Missing code or state from GitHub. Try again.",
  OAUTH_STATE_MISMATCH:
    "That sign-in attempt timed out. Try again - this time finish in one go.",
  OAUTH_TOKEN_EXCHANGE_FAILED:
    "GitHub rejected our token exchange. Refresh and try again.",
  OAUTH_USER_FETCH_FAILED:
    "We couldn't read your GitHub profile. Check the App permissions, then retry.",
  OAUTH_USER_PERSIST_FAILED:
    "We couldn't save your account. The database may be down - try again in a minute.",
  OAUTH_SESSION_FAILED:
    "We couldn't issue your session. Refresh and retry.",
  RATE_LIMITED: "Too many sign-in attempts. Wait a minute and try again.",
};

function readOAuthError() {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const code = params.get("oauth_error");
  if (!code) return null;
  const desc = params.get("desc") || "";
  return { code, desc };
}

function clearOAuthError() {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  url.searchParams.delete("oauth_error");
  url.searchParams.delete("desc");
  window.history.replaceState({}, "", url.toString());
}

export default function Login() {
  const [err, setErr] = useState(null);

  useEffect(() => {
    const found = readOAuthError();
    if (found) {
      setErr(found);
      // strip query so refreshes don't keep showing the banner
      clearOAuthError();
    }
  }, []);

  return (
    <div className="min-h-full flex items-center justify-center px-6">
      <div className="card max-w-md w-full">
        <div className="mb-6">
          <Logo size="md" />
        </div>
        <p className="text-fg-secondary text-sm">We see what you don't.</p>
        <h1 className="mt-6 text-2xl font-semibold tracking-tight">sign in</h1>
        <p className="mt-2 text-fg-secondary text-sm">
          Connect your GitHub account to install basira on a repo.
        </p>

        {err && (
          <div
            data-testid="oauth-error-banner"
            className="mt-4 flex items-start gap-2 rounded border border-danger/40 bg-danger/10 p-3 text-sm"
          >
            <AlertTriangle size={16} className="text-danger mt-0.5 shrink-0" />
            <div className="text-fg-secondary">
              <p className="text-fg" data-testid="oauth-error-message">
                {OAUTH_MESSAGES[err.code] ||
                  "Sign-in failed. Try again, or check the backend logs."}
              </p>
              <p
                className="mt-1 font-mono text-xs text-fg-muted"
                data-testid="oauth-error-code"
              >
                {err.code}
                {err.desc ? ` - ${err.desc}` : ""}
              </p>
            </div>
          </div>
        )}

        <a
          href={githubLoginUrl()}
          className="btn btn-primary w-full justify-center mt-6"
        >
          <Github size={16} />
          <span>{err ? "try again" : "continue with github"}</span>
        </a>
        <p className="mt-4 text-fg-muted text-xs">
          We read your profile, email, and the list of repos you can access.
          You can revoke access anytime in GitHub settings.
        </p>
      </div>
    </div>
  );
}
