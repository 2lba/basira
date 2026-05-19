export default function ApiKeysTab() {
  return (
    <div className="max-w-2xl" data-testid="api-keys-tab">
      <div className="card">
        <h2 className="text-sm uppercase tracking-wider text-fg-muted">
          api keys
        </h2>
        <p className="mt-2 text-fg-secondary text-sm">
          Personal API keys for programmatic access to reviewly will land here.
          Coming in a later release.
        </p>
        <p className="mt-2 text-fg-muted text-xs">No keys to manage yet.</p>
      </div>
    </div>
  );
}
