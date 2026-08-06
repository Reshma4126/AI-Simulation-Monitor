import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Activity, ArrowLeft, Mail, CheckCircle } from "lucide-react";
import "../components/dashboard/dashboard.css";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (email) {
      setSubmitted(true);
    }
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
            Reset Your Password
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Enter your instructor email to receive password reset instructions
          </p>
        </div>

        {!submitted ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">
                Instructor Email Address
              </label>
              <div className="medsim-input-wrapper">
                <Mail className="medsim-input-icon" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="doctor@hospital.org"
                  className="medsim-input-field"
                  style={{ paddingLeft: "42px" }}
                />
              </div>
            </div>

            <button
              type="submit"
              className="w-full h-11 bg-teal-700 hover:bg-teal-800 text-white font-semibold text-sm rounded-xl cursor-pointer shadow-xs transition-colors"
            >
              Send Reset Instructions →
            </button>
          </form>
        ) : (
          <div className="p-4 rounded-xl bg-teal-50 border border-teal-200 text-center space-y-2">
            <CheckCircle className="w-8 h-8 text-teal-700 mx-auto" />
            <h3 className="font-bold text-sm text-teal-900">Check Your Email</h3>
            <p className="text-xs text-teal-700">
              We sent password recovery steps to <strong>{email}</strong>.
            </p>
            <button
              onClick={() => navigate("/reset-password")}
              className="mt-2 w-full py-2 bg-teal-700 hover:bg-teal-800 text-white rounded-lg text-xs font-semibold cursor-pointer"
            >
              Proceed to Reset Password Page →
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
