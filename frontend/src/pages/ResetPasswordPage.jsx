import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Activity, ArrowLeft, Lock, CheckCircle } from "lucide-react";
import "../components/dashboard/dashboard.css";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setError("");
    setSubmitted(true);
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-100 p-4 font-sans text-slate-900">
      <div className="w-full max-w-md bg-white rounded-2xl border border-slate-200 shadow-xl p-8 space-y-6">
        <div className="flex justify-center">
          <div className="w-12 h-12 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700">
            <Activity className="w-7 h-7 stroke-[2.2]" />
          </div>
        </div>

        <div className="text-center">
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Create New Password
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Your new password must be different from previous passwords
          </p>
        </div>

        {!submitted ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">
                New Password
              </label>
              <div className="medsim-input-wrapper">
                <Lock className="medsim-input-icon" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="medsim-input-field"
                  style={{ paddingLeft: "42px" }}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">
                Confirm New Password
              </label>
              <div className="medsim-input-wrapper">
                <Lock className="medsim-input-icon" />
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="medsim-input-field"
                  style={{ paddingLeft: "42px" }}
                />
              </div>
            </div>

            {error && <div className="text-xs text-rose-600 font-semibold">{error}</div>}

            <button
              type="submit"
              className="w-full h-11 bg-teal-700 hover:bg-teal-800 text-white font-semibold text-sm rounded-xl cursor-pointer shadow-xs transition-colors"
            >
              Update Password →
            </button>
          </form>
        ) : (
          <div className="p-4 rounded-xl bg-teal-50 border border-teal-200 text-center space-y-2">
            <CheckCircle className="w-8 h-8 text-teal-700 mx-auto" />
            <h3 className="font-bold text-sm text-teal-900">Password Reset Complete</h3>
            <p className="text-xs text-teal-700">
              Your password has been successfully updated.
            </p>
            <button
              onClick={() => navigate("/")}
              className="mt-2 w-full py-2 bg-teal-700 hover:bg-teal-800 text-white rounded-lg text-xs font-semibold cursor-pointer"
            >
              Back to Sign In →
            </button>
          </div>
        )}

        <div className="pt-4 border-t border-slate-100 text-center">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-teal-700 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Sign In
          </Link>
        </div>
      </div>
    </div>
  );
}
