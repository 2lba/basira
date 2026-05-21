import { Github, ExternalLink } from "lucide-react";

const VERSION = "0.1.0";
const GH_URL = "https://github.com/2lba/basira";
const DOCS_URL = "https://github.com/2lba/basira#readme";
const AUTHOR_URL = "https://github.com/2lba";

export default function About() {
  return (
    <section className="max-w-2xl" data-testid="about-page">
      <h1 className="text-2xl font-semibold tracking-tight">about basira</h1>
      <p className="mt-1 text-fg-secondary text-sm">version {VERSION}</p>

      <div className="mt-6 card">
        <p className="text-fg leading-relaxed">
          Basira is an open source, self-hostable AI code reviewer for GitHub
          pull requests. Free alternative to closed-source review tools, with
          transparent prompts and zero vendor lock-in.
        </p>
      </div>

      <div className="mt-6 card space-y-3">
        <h2 className="text-sm uppercase tracking-wider text-fg-muted">
          links
        </h2>
        <ul className="space-y-2 text-sm">
          <li>
            <a
              data-testid="about-github"
              href={GH_URL}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-2 text-accent hover:underline"
            >
              <Github size={14} />
              source on github
            </a>
          </li>
          <li>
            <a
              data-testid="about-docs"
              href={DOCS_URL}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-2 text-accent hover:underline"
            >
              <ExternalLink size={14} />
              documentation
            </a>
          </li>
        </ul>
      </div>

      <div className="mt-6 card">
        <h2 className="text-sm uppercase tracking-wider text-fg-muted">built by</h2>
        <p className="mt-2 text-fg text-sm">
          <a
            data-testid="about-author"
            href={AUTHOR_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="text-accent hover:underline"
          >
            Abdulaziz AlQahtani
          </a>{" "}
          <span className="text-fg-muted"> -  @2lba</span>
        </p>
      </div>
    </section>
  );
}
