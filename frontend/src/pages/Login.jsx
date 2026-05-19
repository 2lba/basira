import { Github } from "lucide-react";
import { githubLoginUrl } from "../api/client.js";

export default function Login() {
  return (
    <div className="min-h-full flex items-center justify-center px-6">
      <div className="card max-w-md w-full">
        <h1 className="text-2xl font-semibold tracking-tight">sign in</h1>
        <p className="mt-2 text-fg-secondary text-sm">
          Connect your GitHub account to install basira on a repo.
        </p>
        <a
          href={githubLoginUrl()}
          className="btn btn-primary w-full justify-center mt-6"
        >
          <Github size={16} />
          <span>continue with github</span>
        </a>
        <p className="mt-4 text-fg-muted text-xs">
          We only read your profile and email. You can revoke access anytime in
          GitHub settings.
        </p>
      </div>
    </div>
  );
}
