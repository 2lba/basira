import { Github } from "lucide-react";
import { githubLoginUrl } from "../api/client.js";
import Logo from "../components/Logo.jsx";

export default function Login() {
  return (
    <div className="min-h-full flex items-center justify-center px-6">
      <div className="card max-w-md w-full">
        <div className="mb-6">
          <Logo size="md" />
        </div>
        <p className="text-fg-secondary text-sm">We see what you don't.</p>
        <h1 className="mt-6 text-2xl font-semibold tracking-tight">sign in</h1>
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
          We read your profile, email, and the list of repos you can access.
          You can revoke access anytime in GitHub settings.
        </p>
      </div>
    </div>
  );
}
