import { useOutletContext } from "react-router-dom";

export default function AccountTab() {
  const { user } = useOutletContext();
  return (
    <div className="max-w-2xl space-y-6" data-testid="account-tab">
      <div className="card">
        <h2 className="text-sm uppercase tracking-wider text-fg-muted">profile</h2>
        <dl className="mt-3 space-y-3 text-sm">
          <Row label="github user">{user.github_login}</Row>
          <Row label="email">{user.email || "—"}</Row>
          <Row label="basira id" mono>{user.id}</Row>
        </dl>
      </div>

      <div className="card">
        <h2 className="text-sm uppercase tracking-wider text-fg-muted">
          install on more repos
        </h2>
        <p className="mt-2 text-fg-secondary text-sm">
          Use the GitHub App page to grant access to more repositories.
        </p>
      </div>
    </div>
  );
}

function Row({ label, children, mono }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-fg-muted">{label}</dt>
      <dd className={mono ? "font-mono text-xs" : ""}>{children}</dd>
    </div>
  );
}
