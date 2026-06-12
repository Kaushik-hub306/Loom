import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import ObservationsPage from "./pages/ObservationsPage";
import ObservationDetailPage from "./pages/ObservationDetailPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import ActivityPage from "./pages/ActivityPage";
import SettingsPage from "./pages/SettingsPage";
import TeamsPage from "./pages/TeamsPage";
import Layout from "./components/Layout";
import { isAuthenticated } from "./api/client";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/observations" replace />} />
          <Route path="/observations" element={<ObservationsPage />} />
          <Route path="/observations/:id" element={<ObservationDetailPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/activity" element={<ActivityPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/teams" element={<TeamsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/observations" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
