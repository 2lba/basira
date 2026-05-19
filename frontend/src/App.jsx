import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useSession } from "./hooks/useSession.js";
import Layout from "./components/Layout.jsx";
import Login from "./pages/Login.jsx";
import Repos from "./pages/Repos.jsx";
import RepoDetail from "./pages/RepoDetail.jsx";
import Reviews from "./pages/Reviews.jsx";
import ReviewDetail from "./pages/ReviewDetail.jsx";
import ScanDetail from "./pages/ScanDetail.jsx";
import ScanCompare from "./pages/ScanCompare.jsx";
import Scans from "./pages/Scans.jsx";
import SharedScan from "./pages/SharedScan.jsx";
import About from "./pages/About.jsx";
import SettingsLayout from "./pages/settings/SettingsLayout.jsx";
import AccountTab from "./pages/settings/AccountTab.jsx";
import NotificationsTab from "./pages/settings/NotificationsTab.jsx";
import ApiKeysTab from "./pages/settings/ApiKeysTab.jsx";
import Toasts from "./components/Toasts.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <Toasts />
      <Routes>
        <Route path="/shared/:token" element={<SharedScan />} />
        <Route path="/*" element={<AppShell />} />
      </Routes>
    </BrowserRouter>
  );
}

function AppShell() {
  const { user, loading, reload } = useSession();

  if (loading) {
    return (
      <div className="min-h-full flex items-center justify-center">
        <div className="text-fg-muted text-sm">loading...</div>
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  return (
    <Routes>
      <Route element={<Layout user={user} onLogout={reload} />}>
        <Route index element={<Repos />} />
        <Route path="repos/:id" element={<RepoDetail />} />
        <Route path="reviews" element={<Reviews />} />
        <Route path="reviews/:id" element={<ReviewDetail />} />
        <Route path="scans" element={<Scans />} />
        <Route path="scans/compare" element={<ScanCompare />} />
        <Route path="scans/:id" element={<ScanDetail />} />
        <Route path="settings" element={<SettingsLayout />}>
          <Route index element={<AccountTab />} />
          <Route path="notifications" element={<NotificationsTab />} />
          <Route path="api-keys" element={<ApiKeysTab />} />
        </Route>
        <Route path="about" element={<About />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
