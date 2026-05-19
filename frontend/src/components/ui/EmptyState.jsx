export default function EmptyState({ icon, title, body, action, testId }) {
  return (
    <div className="card text-center py-14 px-6" data-testid={testId || "empty-state"}>
      {icon && (
        <div
          className="mx-auto mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-bg border border-border-subtle text-fg-muted"
          aria-hidden="true"
        >
          {icon}
        </div>
      )}
      <h2 className="text-lg font-medium text-fg" data-testid="empty-state-title">
        {title}
      </h2>
      {body && (
        <p className="mt-2 text-fg-secondary text-sm max-w-md mx-auto">{body}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
