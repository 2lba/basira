import { NavLink, Outlet, useOutletContext } from "react-router-dom";

const TABS = [
  { to: "/settings", label: "account", end: true, testId: "tab-account" },
  {
    to: "/settings/notifications",
    label: "notifications",
    testId: "tab-notifications",
  },
  {
    to: "/settings/api-keys",
    label: "api keys",
    testId: "tab-api-keys",
  },
];

export default function SettingsLayout() {
  const ctx = useOutletContext();
  return (
    <section data-testid="settings-page">
      <h1 className="text-2xl font-semibold tracking-tight">settings</h1>
      <p className="mt-1 text-fg-secondary text-sm">
        Manage your profile, notifications and API access.
      </p>
      <nav
        className="mt-6 flex gap-1 border-b border-border-subtle"
        data-testid="settings-tabs"
      >
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            data-testid={t.testId}
            className={({ isActive }) =>
              `px-3 py-2 text-sm border-b-2 -mb-px transition-colors ${
                isActive
                  ? "border-accent text-fg"
                  : "border-transparent text-fg-secondary hover:text-fg"
              }`
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-6">
        <Outlet context={ctx} />
      </div>
    </section>
  );
}
