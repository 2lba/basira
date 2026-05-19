import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, X } from "lucide-react";
import { listApiKeys } from "../api/client.js";

const DISMISS_KEY = "basira_apikey_banner_dismissed";
const REFRESH_EVENT = "basira:api-keys-changed";

export function notifyApiKeysChanged() {
  // ApiKeysTab calls this after a successful add/remove so any mounted
  // banner instance re-checks instead of needing a page reload.
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(REFRESH_EVENT));
  }
}

function isDismissed() {
  try {
    return localStorage.getItem(DISMISS_KEY) === "1";
  } catch {
    return false;
  }
}

function markDismissed() {
  try {
    localStorage.setItem(DISMISS_KEY, "1");
  } catch {
    // localStorage may be blocked — that's fine, user just sees banner again next load
  }
}

function clearDismissed() {
  try {
    localStorage.removeItem(DISMISS_KEY);
  } catch {
    // localStorage may be blocked
  }
}

export default function MissingKeyBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const keys = await listApiKeys();
        const hasAnthropic = (keys || []).some(
          (k) => k.provider === "anthropic" && k.is_valid,
        );
        if (cancelled) return;
        if (hasAnthropic) {
          // user added a key — clear the dismiss flag so the banner
          // reappears if they later remove the key again
          clearDismissed();
          setShow(false);
        } else {
          setShow(!isDismissed());
        }
      } catch {
        // not authed yet; banner stays hidden
      }
    }
    check();
    const handler = () => check();
    window.addEventListener(REFRESH_EVENT, handler);
    return () => {
      cancelled = true;
      window.removeEventListener(REFRESH_EVENT, handler);
    };
  }, []);

  if (!show) return null;

  return (
    <div
      data-testid="missing-key-banner"
      role="status"
      className="bg-warning/10 border-b border-warning/30 text-fg"
    >
      <div className="max-w-content mx-auto px-6 py-3 flex items-center gap-3">
        <AlertTriangle size={16} className="text-warning shrink-0" />
        <span className="flex-1 text-sm">
          Add your Anthropic API key in Settings to enable scanning.
        </span>
        <Link
          to="/settings/api-keys"
          data-testid="missing-key-banner-cta"
          className="btn btn-primary"
        >
          go to settings
        </Link>
        <button
          type="button"
          data-testid="missing-key-banner-dismiss"
          aria-label="dismiss"
          onClick={() => {
            markDismissed();
            setShow(false);
          }}
          className="text-fg-muted hover:text-fg"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
