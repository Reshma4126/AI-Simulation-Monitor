import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, LogOut, ArrowRight, ShieldCheck } from "lucide-react";
import "../components/dashboard/dashboard.css";

export default function StudentDashboardPage() {
  const [sessionCode, setSessionCode] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleJoin = (e) => {
    e.preventDefault();
    if (!sessionCode.trim()) {
      setError("Please enter a valid session code");
      return;
    }
    const code = sessionCode.trim().toUpperCase();
    sessionStorage.setItem("session_code", code);
    navigate(`/monitor/${code}`);
  };

  const handleLogout = () => {
    sessionStorage.clear();
    navigate("/");
  };

  return (
    <div className="flex flex-col min-h-screen bg-slate-50 font-sans text-slate-900">
      {/* Top Header */}
      <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700">
            <Activity className="w-5.5 h-5.5 stroke-[2.2]" />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-slate-900 tracking-tight">MedSim AI</span>
            <span className="text-[10px] font-semibold bg-teal-50 text-teal-700 px-2 py-0.5 rounded-full border border-teal-200 tracking-wide uppercase">
              Student Monitor Portal
            </span>
          </div>
        </div>

        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
        >
          <LogOut className="w-4 h-4" />
          Sign Out
        </button>
      </header>

      {/* Main Student Portal Body */}
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md bg-white rounded-2xl border border-slate-200 shadow-xl p-8 space-y-6">
          <div className="text-center space-y-2">
            <div className="w-12 h-12 rounded-2xl bg-teal-50 border border-teal-200 text-teal-700 flex items-center justify-center mx-auto">
              <ShieldCheck className="w-7 h-7" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Join Active Simulation
            </h1>
            <p className="text-xs text-slate-500">
              Enter the 6-character session code provided by your instructor
            </p>
          </div>

          <form onSubmit={handleJoin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">
                Session Code
              </label>
              <input
                type="text"
                required
                maxLength={6}
                value={sessionCode}
                onChange={(e) => setSessionCode(e.target.value.toUpperCase())}
                placeholder="e.g. SIM123"
                className="w-full h-12 px-4 bg-slate-50 border border-slate-200 focus:border-teal-700 focus:bg-white rounded-xl text-center text-lg font-mono font-bold tracking-widest text-slate-900 outline-none uppercase transition-all"
              />
            </div>

            {error && <div className="text-xs text-rose-600 font-semibold text-center">{error}</div>}

            <button
              type="submit"
              className="w-full h-12 bg-teal-700 hover:bg-teal-800 text-white font-semibold text-sm rounded-xl cursor-pointer shadow-xs flex items-center justify-center gap-2 transition-colors"
            >
              Connect to Monitor →
            </button>
          </form>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-[11px] text-slate-500 text-center">
            🔒 Student Portal Access • Instructor controls strictly restricted
          </div>
        </div>
      </main>
    </div>
  );
}
