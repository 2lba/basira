import { useSession } from "./hooks/useSession.js";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";

export default function App() {
  const { user, loading, reload } = useSession();

  if (loading) {
    return (
      <div className="min-h-full flex items-center justify-center">
        <div className="text-fg-muted text-sm">loading...</div>
      </div>
    );
  }

  if (!user) return <Login />;
  return <Dashboard user={user} onLogout={reload} />;
}
