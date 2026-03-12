import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useAuthStore } from "./store/auth";
import { ToastProvider } from "./components/ui/ToastContext";

import AuthLayout from "./components/layouts/AuthLayout";
import MainLayout from "./components/layouts/MainLayout";
import ProtectedRoute from "./components/ProtectedRoute";

import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import DashboardPage from "./pages/DashboardPage";
import CompetitionsPage from "./pages/CompetitionsPage";
import UsersPage from "./pages/UsersPage";
import TimersPage from "./pages/TimersPage";
import RankingPage from "./pages/RankingPage";
import RegistrationPage from "./pages/RegistrationPage";
import NotFoundPage from "./pages/NotFoundPage";

function AppLoader() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <svg
          className="h-8 w-8 animate-spin text-primary-600"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <p className="text-sm text-gray-400">Carregando...</p>
      </div>
    </div>
  );
}

export default function App() {
  const { initialize, isInitialized } = useAuthStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  if (!isInitialized) {
    return <AppLoader />;
  }

  return (
    <ToastProvider>
    <BrowserRouter>
      <Routes>
        {/* Rota raiz */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        {/* Rotas públicas — layout centralizado */}
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
        </Route>

        {/* Ranking público — sem sidebar (RF-39: sem necessidade de login) */}
        <Route path="/ranking/:competitionId" element={<RankingPage />} />
        <Route path="/competitions/:competitionId/ranking" element={<RankingPage />} />

        {/* Rotas protegidas — todos os roles autenticados */}
        <Route element={<ProtectedRoute />}>
          <Route element={<MainLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/ranking" element={<RankingPage />} />
            <Route path="/inscricao" element={<RegistrationPage />} />
            <Route path="/competitions/:competitionId/inscricao" element={<RegistrationPage />} />

            {/* Timers — judge, operator, admin */}
            <Route
              element={<ProtectedRoute allowedRoles={["judge", "operator", "admin"]} />}
            >
              <Route path="/timers" element={<TimersPage />} />
              <Route path="/competitions/:competitionId/timers" element={<TimersPage />} />
            </Route>

            {/* Gestão — operator, admin */}
            <Route
              element={<ProtectedRoute allowedRoles={["operator", "admin"]} />}
            >
              <Route path="/competitions" element={<CompetitionsPage />} />
              <Route path="/users" element={<UsersPage />} />
            </Route>
          </Route>
        </Route>

        {/* 404 */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
    </ToastProvider>
  );
}
