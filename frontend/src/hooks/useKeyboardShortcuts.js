import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

const G_TIMEOUT_MS = 700;

function isEditable(target) {
  if (!target) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  return false;
}

export function useKeyboardShortcuts({ onScanNow, onOpenHelp }) {
  const navigate = useNavigate();
  const lastG = useRef(0);

  useEffect(() => {
    function handler(e) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (isEditable(e.target)) {
        if (e.key === "Escape") e.target.blur();
        return;
      }

      // search focus
      if (e.key === "/") {
        const el = document.querySelector(
          'input[type="search"], [data-shortcut="search"]',
        );
        if (el) {
          e.preventDefault();
          el.focus();
        }
        return;
      }

      // help modal — accept both "?" key and Shift+Slash
      if (e.key === "?" || (e.key === "/" && e.shiftKey)) {
        e.preventDefault();
        onOpenHelp && onOpenHelp();
        return;
      }

      // n -> new scan
      if (e.key === "n") {
        if (onScanNow) {
          e.preventDefault();
          onScanNow();
        }
        return;
      }

      // g sequences
      const now = Date.now();
      if (e.key === "g") {
        lastG.current = now;
        return;
      }
      if (lastG.current && now - lastG.current < G_TIMEOUT_MS) {
        const k = e.key.toLowerCase();
        lastG.current = 0;
        if (k === "r") {
          e.preventDefault();
          navigate("/");
        } else if (k === "h") {
          e.preventDefault();
          navigate("/scans");
        } else if (k === "s") {
          e.preventDefault();
          navigate("/settings");
        } else if (k === "a") {
          e.preventDefault();
          navigate("/about");
        }
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [navigate, onScanNow, onOpenHelp]);
}
