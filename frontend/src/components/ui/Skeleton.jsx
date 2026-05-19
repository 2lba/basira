export function SkeletonLine({ width = "100%", height = 14, className = "" }) {
  return (
    <div
      className={`bg-border-subtle/80 rounded animate-pulse ${className}`}
      style={{ width, height }}
      data-testid="skeleton-line"
    />
  );
}

export function SkeletonCard({ lines = 2 }) {
  return (
    <div className="card space-y-3 animate-pulse" data-testid="skeleton-card">
      <SkeletonLine width="40%" height={16} />
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonLine key={i} width={i === lines - 1 ? "60%" : "100%"} />
      ))}
    </div>
  );
}

export function SkeletonRows({ count = 3 }) {
  return (
    <ul className="space-y-2" data-testid="skeleton-rows">
      {Array.from({ length: count }).map((_, i) => (
        <li key={i} className="card h-16 animate-pulse" />
      ))}
    </ul>
  );
}

export function SkeletonHeader() {
  return (
    <div className="space-y-2" data-testid="skeleton-header">
      <SkeletonLine width="200px" height={24} />
      <SkeletonLine width="320px" height={12} />
    </div>
  );
}
