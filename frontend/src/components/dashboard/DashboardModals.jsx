import React from "react";
import { X, BookOpen, FileText, Settings, ClipboardList } from "lucide-react";

export default function DashboardModals({
  activeModal,
  onClose,
  handleStartSimulation,
  initialSessions,
}) {
  if (!activeModal) return null;

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-5">
      {/* SCENARIO LIBRARY MODAL */}
      {activeModal === "library" && (
        <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto shadow-2xl p-6 flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-teal-700" />
                Clinical Scenario Library
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                Select a pre-configured simulation scenario to launch
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-500 cursor-pointer transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex flex-col gap-3">
            {[
              { name: "VF Cardiac Arrest", difficulty: "High", system: "Cardiovascular", duration: "15 min" },
              { name: "Anaphylactic Shock", difficulty: "Critical", system: "Immunology / Respiratory", duration: "20 min" },
              { name: "Acute STEMI with AV Block", difficulty: "High", system: "Cardiovascular", duration: "25 min" },
              { name: "Pediatric Asthma Exacerbation", difficulty: "Medium", system: "Pediatric Respiratory", duration: "15 min" },
              { name: "Sepsis & Septic Shock", difficulty: "High", system: "Multisystem / ICU", duration: "30 min" },
            ].map((item, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50 flex items-center justify-between"
              >
                <div>
                  <div className="font-bold text-sm text-slate-900">{item.name}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {item.system} • Est. {item.duration}
                  </div>
                </div>
                <button
                  onClick={handleStartSimulation}
                  className="bg-teal-700 hover:bg-teal-800 text-white rounded-lg px-4 py-2 text-xs font-semibold cursor-pointer transition-colors"
                >
                  Select & Start →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* DEBRIEF REPORTS MODAL */}
      {activeModal === "reports" && (
        <div className="bg-white rounded-2xl w-full max-w-xl shadow-2xl p-6 flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <FileText className="w-5 h-5 text-teal-700" />
                Automated Debrief Reports
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                AI-generated clinical performance analytics & transcripts
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-500 cursor-pointer transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="bg-teal-50 border border-teal-200 p-4 rounded-xl text-xs text-teal-800">
            <strong className="font-bold">Latest Completed Debrief Summary:</strong>
            <div className="mt-2 text-slate-700 leading-relaxed">
              Session: VF Cardiac Arrest (06 Aug 2026) <br />
              CPR Start Time: 42 sec (Target: &lt;60s) — <strong className="text-emerald-700">Pass</strong> <br />
              Defibrillation latency: 1 min 14 sec — <strong className="text-emerald-700">Optimal</strong> <br />
              Overall Score: <strong className="text-teal-800 font-bold">94 / 100</strong>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-full bg-teal-700 hover:bg-teal-800 text-white rounded-xl py-2.5 text-xs font-semibold cursor-pointer transition-colors"
          >
            Close Reports Preview
          </button>
        </div>
      )}

      {/* SETTINGS MODAL */}
      {activeModal === "settings" && (
        <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl p-6 flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Settings className="w-5 h-5 text-teal-700" />
              Instructor System Settings
            </h3>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-500 cursor-pointer transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex flex-col gap-4 text-xs font-medium text-slate-700">
            <div className="flex items-center justify-between">
              <span>Audio Alarm Alerts</span>
              <input type="checkbox" defaultChecked className="accent-teal-700 w-4 h-4" />
            </div>
            <div className="flex items-center justify-between">
              <span>Automatic AI Debrief Generation</span>
              <input type="checkbox" defaultChecked className="accent-teal-700 w-4 h-4" />
            </div>
            <div className="flex items-center justify-between">
              <span>Student Remote Portal Access</span>
              <input type="checkbox" defaultChecked className="accent-teal-700 w-4 h-4" />
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-full bg-teal-700 hover:bg-teal-800 text-white rounded-xl py-2.5 text-xs font-semibold cursor-pointer transition-colors"
          >
            Save Preferences
          </button>
        </div>
      )}

      {/* SESSIONS LIST MODAL */}
      {activeModal === "sessions" && (
        <div className="bg-white rounded-2xl w-full max-w-2xl shadow-2xl p-6 flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <ClipboardList className="w-5 h-5 text-teal-700" />
                All Simulation Sessions
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                Complete history of active and completed simulation runs
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-500 cursor-pointer transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex flex-col gap-2.5 max-h-96 overflow-y-auto pr-1">
            {initialSessions.map((session) => (
              <div
                key={session.id}
                className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 flex items-center justify-between"
              >
                <div>
                  <div className="font-bold text-sm text-slate-900">{session.name}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {session.date} • {session.duration} • Patient: {session.patient}
                  </div>
                </div>
                <button
                  onClick={() => {
                    onClose();
                    handleStartSimulation();
                  }}
                  className="bg-teal-700 hover:bg-teal-800 text-white rounded-lg px-3.5 py-1.5 text-xs font-semibold cursor-pointer transition-colors"
                >
                  Open Session →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
