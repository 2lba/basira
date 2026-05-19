import { NavLink, Outlet } from "react-router-dom";
import { LogOut, GitPullRequest, GitBranch, Settings } from "lucide-react";
import { logout } from "../api/client.js";

export default function Layout({ user, onLogout }) {
  async function handleLogout() {
    try {
      await logout();
    } finally {
      onLogout?.();
    }
  }

  return (
    <div className="min-h-full flex">
      <aside className="w-60 border-r border-border-subtle flex flex-col">
        <div className="px-6 py-5 border-b border-border-subtle">
          <span className="text-fg font-semibold tracking-tight">reviewly</span>
          <span className="ml-2 text-fg-muted text-xs">v0.1.0</span>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          <NavItem to="/" icon={<GitBranch size={16} />} label="repositories" end />
          <NavItem to="/reviews" icon={<GitPullRequest size={16} />} label="reviews" />
          <NavItem to="/settings" icon={<Settings size={16} />} label="account" />
        </nav>
        <div className="border-t border-border-subtle px-3 py-3">
          <div className="flex items-center gap-2 px-2 py-2 text-sm">
            {user.avatar_url && (
              <img
                src={user.avatar_url}
                alt=""
                className="w-6 h-6 rounded-full border border-border-subtle"
              />
            )}
            <span className="text-fg-secondary truncate">{user.github_login}</span>
          </div>
          <button onClick={handleLogout} className="btn btn-ghost w-full justify-start">
            <LogOut size={14} />
            <span>sign out</span>
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="max-w-content mx-auto px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function NavItem({ to, icon, label, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors ${
          isActive
            ? "bg-surface text-fg"
            : "text-fg-secondary hover:bg-surface hover:text-fg"
        }`
      }
    >
      {icon}
      <span>{label}</span>
    </NavLink>
  );
}
