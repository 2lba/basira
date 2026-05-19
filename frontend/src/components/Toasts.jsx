import { useEffect, useState } from "react";
import { X, AlertTriangle, RefreshCw } from "lucide-react";

const listeners = new Set();
let nextId = 1;

export function showToast({ message, retry = null, ttl = 6000 } = {}) {
  const id = nextId++;
  const toast = { id, message: String(message || "Something went wrong"), retry, ttl };
  for (const fn of listeners) fn({ type: "add", toast });
  if (ttl > 0) {
    setTimeout(() => dismissToast(id), ttl);
  }
  return id;
}

export function dismissToast(id) {
  for (const fn of listeners) fn({ type: "remove", id });
}

export default function Toasts() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    function on(evt) {
      if (evt.type === "add") {
        setItems((prev) => [...prev, evt.toast]);
      } else if (evt.type === "remove") {
        setItems((prev) => prev.filter((t) => t.id !== evt.id));
      }
    }
    listeners.add(on);
    return () => {
      listeners.delete(on);
    };
  }, []);

  if (items.length === 0) return null;

  return (
    <div
      className="fixed bottom-6 left-6 z-50 flex flex-col gap-2 max-w-sm"
      data-testid="toast-stack"
    >
      {items.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}

function ToastItem({ toast }) {
  const [busy, setBusy] = useState(false);

  async function onRetry() {
    setBusy(true);
    try {
      await toast.retry();
    } finally {
      setBusy(false);
      dismissToast(toast.id);
    }
  }

  return (
    <div
      role="status"
      data-testid="toast"
      className="card border-danger/40 shadow-lg flex items-start gap-3 min-w-[280px]"
    >
      <AlertTriangle size={16} className="text-danger mt-0.5" />
      <div className="flex-1">
        <p className="text-sm text-fg" data-testid="toast-message">
          {toast.message}
        </p>
      </div>
      <div className="flex items-center gap-1">
        {toast.retry && (
          <button
            type="button"
            data-testid="toast-retry"
            onClick={onRetry}
            disabled={busy}
            className="inline-flex items-center gap-1 text-xs text-accent hover:underline disabled:opacity-50"
          >
            <RefreshCw size={12} />
            <span>{busy ? "..." : "retry"}</span>
          </button>
        )}
        <button
          type="button"
          aria-label="dismiss"
          data-testid="toast-dismiss"
          onClick={() => dismissToast(toast.id)}
          className="text-fg-muted hover:text-fg"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
