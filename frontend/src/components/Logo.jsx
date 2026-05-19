/**
 * Basira wordmark with an accent line + focal dot underneath.
 *
 * The accent is rendered as an SVG with a fixed viewBox so it scales
 * proportionally with the wordmark size. The wordmark itself uses
 * Space Grotesk via the global font stack.
 */

const SIZES = {
  sm: { fontPx: 24, gapPx: 6, accentHeight: 6 },
  md: { fontPx: 48, gapPx: 10, accentHeight: 12 },
  lg: { fontPx: 96, gapPx: 14, accentHeight: 20 },
};

const ACCENT_COLOR = "#06b6d4"; // cyan-500
const WORDMARK_VAR = "var(--basira-wordmark, #fafafa)";

export default function Logo({
  size = "md",
  withAccent = true,
  className = "",
}) {
  const cfg = SIZES[size] || SIZES.md;
  return (
    <span
      data-testid="basira-logo"
      data-size={size}
      className={`inline-flex flex-col items-start ${className}`}
      style={{ lineHeight: 1 }}
    >
      <span
        className="font-display"
        style={{
          fontFamily:
            '"Space Grotesk", system-ui, -apple-system, sans-serif',
          fontWeight: 500,
          letterSpacing: "-0.04em",
          fontSize: `${cfg.fontPx}px`,
          color: WORDMARK_VAR,
        }}
      >
        Basira
      </span>
      {withAccent && (
        <span
          data-testid="basira-logo-accent"
          aria-hidden="true"
          style={{
            display: "block",
            width: "100%",
            marginTop: `${cfg.gapPx}px`,
          }}
        >
          <Accent height={cfg.accentHeight} />
        </span>
      )}
    </span>
  );
}

function Accent({ height }) {
  // viewBox is intentionally 100 wide so widths map to "percent of wordmark"
  // and the SVG scales width:100% to match the text above.
  const VB_W = 100;
  const VB_H = 12;
  const strokeW = 1.6; // in viewBox units → looks ~4–5px once scaled
  const dotR = 2.4;
  return (
    <svg
      width="100%"
      height={height}
      viewBox={`0 0 ${VB_W} ${VB_H}`}
      preserveAspectRatio="none"
      style={{ display: "block", overflow: "visible" }}
    >
      <line
        x1="0"
        y1={VB_H / 2}
        x2="48"
        y2={VB_H / 2}
        stroke={ACCENT_COLOR}
        strokeWidth={strokeW}
        strokeLinecap="round"
      />
      <circle cx="55" cy={VB_H / 2} r={dotR} fill={ACCENT_COLOR} />
      <line
        x1="62"
        y1={VB_H / 2}
        x2="95"
        y2={VB_H / 2}
        stroke={ACCENT_COLOR}
        strokeWidth={strokeW}
        strokeLinecap="round"
      />
    </svg>
  );
}
