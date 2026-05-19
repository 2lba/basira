const SEV_ORDER = ["critical", "major", "minor", "nit"];

export function buildScanMarkdown(scan) {
  const repo = scan.repo_full_name || "unknown";
  const sha = scan.head_sha ? scan.head_sha.slice(0, 7) : null;
  const finishedAt = scan.finished_at
    ? new Date(scan.finished_at).toISOString()
    : new Date(scan.created_at).toISOString();
  const ghBase = `https://github.com/${repo}`;
  const ref = scan.head_sha || "HEAD";

  const lines = [];
  lines.push(`# Scan report — ${repo}`);
  lines.push("");
  lines.push(`- Date: ${finishedAt}`);
  if (sha) lines.push(`- Commit: \`${sha}\``);
  if (scan.ref) lines.push(`- Branch: \`${scan.ref}\``);
  if (scan.model) lines.push(`- Model: \`${scan.model}\``);
  lines.push(`- Status: ${scan.status}`);
  lines.push(`- Score: **${scan.score ?? "—"} / 100**`);
  if (scan.files_scanned != null) {
    lines.push(`- Files scanned: ${scan.files_scanned}`);
  }
  if (scan.counts) {
    const c = scan.counts;
    lines.push(
      `- Findings: ${c.total || 0} (${c.critical || 0} critical, ${c.major || 0} major, ${c.minor || 0} minor, ${c.nit || 0} nit)`,
    );
  }
  lines.push("");
  if (scan.summary) {
    lines.push("## Summary");
    lines.push("");
    lines.push(scan.summary);
    lines.push("");
  }

  const findings = scan.findings || [];
  if (findings.length === 0) {
    lines.push("## Findings");
    lines.push("");
    lines.push("No issues found.");
    lines.push("");
  } else {
    const groups = groupBy(findings, "severity");
    for (const sev of SEV_ORDER) {
      const items = groups[sev] || [];
      if (items.length === 0) continue;
      lines.push(`## ${capitalize(sev)} (${items.length})`);
      lines.push("");
      for (const f of items) {
        const loc = f.line ? `${f.path}:${f.line}` : f.path;
        const ghUrl = buildGithubUrl(ghBase, ref, f.path, f.line);
        lines.push(`### \`${loc}\` — ${f.category}`);
        lines.push("");
        lines.push(f.message);
        lines.push("");
        if (f.suggestion) {
          lines.push("```");
          lines.push(f.suggestion);
          lines.push("```");
          lines.push("");
        }
        if (ghUrl) {
          lines.push(`[view on github](${ghUrl})`);
          lines.push("");
        }
      }
    }
  }
  return lines.join("\n");
}

function buildGithubUrl(base, ref, path, line) {
  if (!base || !path) return null;
  return `${base}/blob/${ref}/${path}${line ? `#L${line}` : ""}`;
}

function groupBy(arr, key) {
  return arr.reduce((acc, item) => {
    (acc[item[key]] = acc[item[key]] || []).push(item);
    return acc;
  }, {});
}

function capitalize(s) {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

export function downloadMarkdown(scan) {
  const text = buildScanMarkdown(scan);
  const shortSha = scan.head_sha ? scan.head_sha.slice(0, 7) : "scan";
  const safeRepo = (scan.repo_full_name || "scan").replace(/[^a-z0-9]+/gi, "-");
  const filename = `${safeRepo}-${shortSha}.md`;
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 0);
  return { filename, text };
}
