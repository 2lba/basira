import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { getPublicScan } from "../api/client.js";
import { ScoreCircle, SeverityBadge } from "../components/features/ScanCard.jsx";

const SEV_ORDER = ["critical", "major", "minor", "nit"];

export default function SharedScan() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getPublicScan(token)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setErr(e.status === 404 ? "Link not found or revoked." : e.message));
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (err) {
    return (
      <main className="min-h-full flex items-center justify-center p-8">
        <div className="card max-w-md text-center" data-testid="shared-not-found">
          <h1 className="text-lg font-medium text-danger">{err}</h1>
        </div>
      </main>
    );
  }
  if (!data) {
    return (
      <main className="min-h-full flex items-center justify-center p-8">
        <div className="text-fg-muted">loading...</div>
      </main>
    );
  }

  const groups = groupBy(data.findings, "severity");
  const ghBase = `https://github.com/${data.repo_full_name}`;
  const ref = data.head_sha || "HEAD";

  return (
    <main className="min-h-full">
      <div className="max-w-content mx-auto px-8 py-10">
        <header className="border-b border-border-subtle pb-6 mb-6 flex items-center justify-between">
          <span className="text-fg font-semibold tracking-tight">reviewly</span>
          <span className="text-fg-muted text-xs">shared scan report</span>
        </header>

        <section data-testid="shared-scan">
          <h1 className="text-2xl font-semibold tracking-tight">scan report</h1>
          <p className="mt-1 text-fg-secondary text-sm font-mono">
            {data.repo_full_name}
            {data.head_sha ? ` · ${data.head_sha.slice(0, 7)}` : ""}
            {data.ref ? ` · ${data.ref}` : ""}
          </p>

          <div className="mt-6 card flex items-start gap-6">
            <ScoreCircle score={data.score} />
            <div className="flex-1">
              <h2 className="text-sm uppercase tracking-wider text-fg-muted">
                summary
              </h2>
              <p className="mt-2 text-fg leading-relaxed">
                {data.summary || "—"}
              </p>
              <dl className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                <Stat label="files" value={data.files_scanned ?? "—"} />
                <Stat label="model" value={data.model || "—"} />
                <Stat
                  label="critical"
                  value={(data.counts && data.counts.critical) || 0}
                />
                <Stat
                  label="total"
                  value={(data.counts && data.counts.total) || 0}
                />
              </dl>
            </div>
          </div>

          <h2 className="mt-8 text-sm uppercase tracking-wider text-fg-muted">
            findings ({data.findings.length})
          </h2>
          {data.findings.length === 0 ? (
            <p className="mt-4 text-fg-secondary">No issues found.</p>
          ) : (
            <div className="mt-4 space-y-6">
              {SEV_ORDER.map((sev) =>
                groups[sev] && groups[sev].length > 0 ? (
                  <div key={sev}>
                    <h3 className="text-xs uppercase tracking-wider text-fg-muted mb-2">
                      {sev} ({groups[sev].length})
                    </h3>
                    <ul className="space-y-3">
                      {groups[sev].map((f, i) => (
                        <li
                          key={`${f.path}:${f.line}:${i}`}
                          className="card"
                          data-testid="shared-finding"
                        >
                          <div className="flex items-center gap-3 flex-wrap">
                            <SeverityBadge severity={f.severity} />
                            <span className="font-mono text-xs text-fg-secondary">
                              {f.path}
                              {f.line ? `:${f.line}` : ""}
                            </span>
                            <span className="text-fg-muted text-xs">
                              {f.category}
                            </span>
                          </div>
                          <p className="mt-2 text-fg text-sm">{f.message}</p>
                          {f.suggestion && (
                            <pre className="mt-2 bg-bg border border-border-subtle rounded p-3 text-xs overflow-x-auto">
                              <code>{f.suggestion}</code>
                            </pre>
                          )}
                          <a
                            href={`${ghBase}/blob/${ref}/${f.path}${f.line ? `#L${f.line}` : ""}`}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="mt-3 inline-flex items-center gap-1 text-xs text-accent hover:underline"
                          >
                            <ExternalLink size={12} /> view on github
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null,
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-fg-muted uppercase tracking-wider">{label}</div>
      <div className="text-fg text-sm font-mono mt-1">{value}</div>
    </div>
  );
}

function groupBy(arr, key) {
  return (arr || []).reduce((acc, item) => {
    (acc[item[key]] = acc[item[key]] || []).push(item);
    return acc;
  }, {});
}
