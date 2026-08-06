import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import RegistrationRequestPage from "./pages/RegistrationRequestPage";
import DashboardPage from "./pages/DashboardPage";
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
    <BrowserRouter>
      <Routes>
        {/* Authentication Flow */}
        <Route path="/" element={<Login />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/register" element={<RegistrationRequestPage />} />

        {/* Instructor Workflow */}
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/cases" element={<CaseLibraryPage />} />
        <Route path="/library" element={<CaseLibraryPage />} />
        <Route path="/initializing" element={<SimulationInitializingPage />} />
        <Route path="/instructor" element={<InstructorDashboard />} />
        <Route path="/completed" element={<SimulationCompletedPage />} />
        <Route path="/debrief" element={<DebriefPage />} />
        <Route path="/sessions" element={<SessionsPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/profile" element={<ProfilePage />} />

        {/* Student Workflow */}
        <Route path="/student-dashboard" element={<StudentDashboardPage />} />
        <Route path="/monitor/:sessionCode" element={<StudentMonitor />} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
