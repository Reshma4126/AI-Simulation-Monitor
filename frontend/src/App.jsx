import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";

import Login from "./pages/Login";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import RegistrationRequestPage from "./pages/RegistrationRequestPage";
import DashboardPage from "./pages/DashboardPage";
import ScenarioStudioPage from "./pages/ScenarioStudioPage";
import CaseLibraryPage from "./pages/CaseLibraryPage";
import SimulationInitializingPage from "./pages/SimulationInitializingPage";
import SimulationCompletedPage from "./pages/SimulationCompletedPage";
import SessionsPage from "./pages/SessionsPage";
import DebriefPage from "./pages/DebriefPage";
import ReportsPage from "./pages/ReportsPage";
import SettingsPage from "./pages/SettingsPage";
import ProfilePage from "./pages/ProfilePage";
import StudentDashboardPage from "./pages/StudentDashboardPage";
import StudentMonitor from "./pages/StudentMonitor";
import InstructorDashboard from "./pages/InstructorDashboard";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Authentication Flow */}
          <Route path="/" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/register" element={<RegistrationRequestPage />} />

          {/* Instructor Workflow (Protected) */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute allowedRoles={["instructor"]}>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases"
            element={
              <ProtectedRoute allowedRoles={["instructor"]}>
                <ScenarioStudioPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/library"
            element={
              <ProtectedRoute allowedRoles={["instructor"]}>
                <CaseLibraryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/initializing"
            element={
              <ProtectedRoute allowedRoles={["instructor"]}>
                <SimulationInitializingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/instructor"
            element={
              <ProtectedRoute allowedRoles={["instructor"]}>
                <InstructorDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/completed"
            element={
              <ProtectedRoute allowedRoles={["instructor"]}>
                <SimulationCompletedPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/sessions"
            element={
              <ProtectedRoute allowedRoles={["instructor"]}>
                <SessionsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/reports"
            element={
              <ProtectedRoute allowedRoles={["instructor"]}>
                <ReportsPage />
              </ProtectedRoute>
            }
          />

          {/* Shared Authenticated Routes (Instructor & Student) */}
          <Route
            path="/debrief"
            element={
              <ProtectedRoute allowedRoles={["instructor", "student"]}>
                <DebriefPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/debrief/:sessionCode"
            element={
              <ProtectedRoute allowedRoles={["instructor", "student"]}>
                <DebriefPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute allowedRoles={["instructor", "student"]}>
                <SettingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute allowedRoles={["instructor", "student"]}>
                <ProfilePage />
              </ProtectedRoute>
            }
          />

          {/* Student Workflow (Protected) */}
          <Route
            path="/student-dashboard"
            element={
              <ProtectedRoute allowedRoles={["student"]}>
                <StudentDashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/monitor/:sessionCode"
            element={
              <ProtectedRoute allowedRoles={["student", "instructor"]}>
                <StudentMonitor />
              </ProtectedRoute>
            }
          />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
