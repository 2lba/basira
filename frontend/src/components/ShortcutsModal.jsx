import { X } from "lucide-react";

const SHORTCUTS = [
  { keys: ["/"], label: "focus search" },
  { keys: ["g", "r"], label: "go to repositories" },
  { keys: ["g", "h"], label: "go to scans history" },
  { keys: ["g", "s"], label: "go to settings" },
  { keys: ["g", "a"], label: "go to about" },
  { keys: ["n"], label: "start scan (on repo page)" },
  { keys: ["?"], label: "open this dialog" },
  { keys: ["esc"], label: "close dialog or unfocus input" },
];

export default function ShortcutsModal({ open, onClose }) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      data-testid="shortcuts-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="card max-w-md w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-lg font-medium">keyboard shortcuts</h3>
          <button
            type="button"
            aria-label="close"
            onClick={onClose}
            className="text-fg-muted hover:text-fg"
          >
            <X size={16} />
          </button>
        </div>
        <ul className="mt-4 space-y-2 text-sm">
          {SHORTCUTS.map((s, i) => (
            <li
              key={i}
              className="flex items-center justify-between gap-4"
              data-testid="shortcut-row"
            >
              <span className="text-fg-secondary">{s.label}</span>
              <span className="flex gap-1">
                {s.keys.map((k, j) => (
                  <kbd
                    key={j}
                    className="font-mono text-xs px-2 py-0.5 rounded bg-bg border border-border-subtle text-fg"
                  >
                    {k}
                  </kbd>
                ))}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
