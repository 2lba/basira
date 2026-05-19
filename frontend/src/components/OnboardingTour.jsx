import { useEffect, useState } from "react";
import { X, ArrowRight } from "lucide-react";

const STORAGE_KEY = "reviewly_tour_completed";

const STEPS = [
  {
    title: "welcome to reviewly",
    body: "These are the GitHub repositories you've connected. Each row is a repo you can review with AI.",
  },
  {
    title: "open a repo",
    body: "Click any repo to see its history, configure rules, and start a scan.",
  },
  {
    title: "scan and review",
    body: "Inside a repo, press the \"scan now\" button (or hit n) to start an AI review of the whole codebase.",
  },
];

export function isTourDone() {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function markTourDone() {
  try {
    localStorage.setItem(STORAGE_KEY, "1");
  } catch {
    // localStorage may be unavailable; nothing to do
  }
}

export default function OnboardingTour({ onDismiss }) {
  const [step, setStep] = useState(0);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(!isTourDone());
  }, []);

  if (!open) return null;
  const last = step === STEPS.length - 1;

  function next() {
    if (last) {
      finish();
    } else {
      setStep((s) => s + 1);
    }
  }
  function finish() {
    markTourDone();
    setOpen(false);
    onDismiss && onDismiss();
  }

  const s = STEPS[step];

  return (
    <div
      role="dialog"
      aria-modal="false"
      data-testid="onboarding-tour"
      className="fixed bottom-6 right-6 z-40 max-w-sm card shadow-lg"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p
            className="text-xs uppercase tracking-wider text-fg-muted"
            data-testid="tour-step"
          >
            step {step + 1} of {STEPS.length}
          </p>
          <h3 className="mt-1 text-base font-medium" data-testid="tour-title">
            {s.title}
          </h3>
        </div>
        <button
          type="button"
          aria-label="skip tour"
          data-testid="tour-skip"
          onClick={finish}
          className="text-fg-muted hover:text-fg"
        >
          <X size={14} />
        </button>
      </div>
      <p className="mt-2 text-fg-secondary text-sm" data-testid="tour-body">
        {s.body}
      </p>
      <div className="mt-4 flex items-center justify-between">
        <div className="flex gap-1" aria-hidden="true">
          {STEPS.map((_, i) => (
            <span
              key={i}
              className={`h-1 w-6 rounded ${
                i <= step ? "bg-accent" : "bg-border-subtle"
              }`}
            />
          ))}
        </div>
        <button
          type="button"
          data-testid="tour-next"
          onClick={next}
          className="btn btn-primary"
        >
          <span>{last ? "got it" : "next"}</span>
          {!last && <ArrowRight size={14} />}
        </button>
      </div>
    </div>
  );
}
