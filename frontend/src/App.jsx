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
import Account from "./pages/Account.jsx";

export default function App() {
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
    <BrowserRouter>
      <Routes>
        <Route element={<Layout user={user} onLogout={reload} />}>
          <Route index element={<Repos />} />
          <Route path="repos/:id" element={<RepoDetail />} />
          <Route path="reviews" element={<Reviews />} />
          <Route path="reviews/:id" element={<ReviewDetail />} />
          <Route path="scans" element={<Scans />} />
          <Route path="scans/compare" element={<ScanCompare />} />
          <Route path="scans/:id" element={<ScanDetail />} />
          <Route path="settings" element={<Account user={user} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
