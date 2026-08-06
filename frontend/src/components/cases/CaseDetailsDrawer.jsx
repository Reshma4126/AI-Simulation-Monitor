import React from "react";
import { X, Play, Heart, Activity, Thermometer, Wind, AlertCircle } from "lucide-react";
import { PatientBadge, DifficultyBadge } from "./PatientBadge";

export default function CaseDetailsDrawer({ selectedCase, onClose, onStartSimulation }) {
  if (!selectedCase) return null;

  const {
    patientName,
    age,
    gender,
    heightCm,
    weightKg,
    bloodGroup,
    chiefComplaint,
    diagnosis,
    medicalHistory,
    symptoms,
    monitorValues,
    difficulty,
    category,
  } = selectedCase;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop Overlay */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity duration-300"
      />

      {/* Right-side Sliding Drawer */}
      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-lg bg-white border-l border-slate-200 shadow-2xl flex flex-col justify-between overflow-hidden">
          {/* Header */}
          <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-teal-700 text-white font-bold text-sm flex items-center justify-center">
                {patientName ? patientName.split(" ").map(n => n[0]).join("").substring(0, 2) : "PT"}
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900 leading-tight">
                  {patientName}
                </h2>
                <div className="flex items-center gap-2 mt-1">
                  <PatientBadge age={`${age} Yrs`} gender={gender} />
                  <DifficultyBadge difficulty={difficulty} />
                </div>
              </div>
            </div>

            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-white hover:bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-500 cursor-pointer transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Drawer Body (Scrollable) */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Diagnosis Banner */}
            <div className="p-4 rounded-xl bg-teal-50 border border-teal-200 text-xs">
              <div className="font-bold text-teal-900 text-sm">{diagnosis}</div>
              <div className="text-teal-700 mt-1">
                Category: <strong>{category}</strong> • Duration: 30 mins
              </div>
            </div>

            {/* Patient Details Grid */}
            <section className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Patient Demographics & Vitals Summary
              </h3>
              <div className="grid grid-cols-3 gap-3 p-4 bg-slate-50 rounded-xl border border-slate-100 text-xs">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Height</span>
                  <span className="font-bold text-slate-800">{heightCm || 170} cm</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Weight</span>
                  <span className="font-bold text-slate-800">{weightKg || 70} kg</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Blood Group</span>
                  <span className="font-bold text-slate-800">{bloodGroup || "O+"}</span>
                </div>
              </div>
            </section>

            {/* Clinical Overview */}
            <section className="space-y-3 text-xs">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Clinical Overview
              </h3>

              <div className="space-y-2">
                <div className="p-3 bg-white rounded-xl border border-slate-200">
                  <span className="text-slate-400 font-semibold block text-[10px] uppercase mb-0.5">
                    Chief Complaint
                  </span>
                  <span className="text-slate-800 font-medium">{chiefComplaint}</span>
                </div>

                <div className="p-3 bg-white rounded-xl border border-slate-200">
                  <span className="text-slate-400 font-semibold block text-[10px] uppercase mb-0.5">
                    Medical History
                  </span>
                  <span className="text-slate-800 font-medium">
                    {medicalHistory && medicalHistory.length > 0
                      ? medicalHistory.join(", ")
                      : "No prior medical history reported"}
                  </span>
                </div>

                <div className="p-3 bg-white rounded-xl border border-slate-200">
                  <span className="text-slate-400 font-semibold block text-[10px] uppercase mb-0.5">
                    Reported Symptoms
                  </span>
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {symptoms && Array.isArray(symptoms) ? (
                      symptoms.map((s, i) => (
                        <span key={i} className="px-2 py-0.5 bg-slate-100 text-slate-700 rounded-md font-medium text-[11px]">
                          {s}
                        </span>
                      ))
                    ) : (
                      <span className="text-slate-600">Chest Pain, Shortness of Breath</span>
                    )}
                  </div>
                </div>
              </div>
            </section>

            {/* Initial Readings (Vitals Monitor Values) */}
            <section className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-teal-700" />
                Initial Monitor Readings
              </h3>

              <div className="grid grid-cols-2 gap-3 text-xs">
                {/* HR */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-slate-400 text-[10px] font-semibold uppercase">HR (Heart Rate)</div>
                  <div className="text-lg font-extrabold text-slate-900 mt-0.5">
                    {monitorValues?.heartRate || 108} <span className="text-xs font-normal text-slate-500">bpm</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5 truncate">
                    {monitorValues?.ecgRhythm || "Sinus Tachycardia"}
                  </div>
                </div>

                {/* BP */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-slate-400 text-[10px] font-semibold uppercase">BP (Blood Pressure)</div>
                  <div className="text-lg font-extrabold text-slate-900 mt-0.5">
                    {monitorValues?.bloodPressure || "150/95"} <span className="text-xs font-normal text-slate-500">mmHg</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Non-invasive NIBP</div>
                </div>

                {/* SpO2 */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-slate-400 text-[10px] font-semibold uppercase">SpO₂ (Pulse Oximetry)</div>
                  <div className="text-lg font-extrabold text-slate-900 mt-0.5">
                    {monitorValues?.spo2 || 94} <span className="text-xs font-normal text-slate-500">%</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Room Air</div>
                </div>

                {/* RR */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-slate-400 text-[10px] font-semibold uppercase">RR (Resp Rate)</div>
                  <div className="text-lg font-extrabold text-slate-900 mt-0.5">
                    {monitorValues?.respiratoryRate || 24} <span className="text-xs font-normal text-slate-500">rpm</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Spontaneous</div>
                </div>

                {/* EtCO2 */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-slate-400 text-[10px] font-semibold uppercase">EtCO₂</div>
                  <div className="text-lg font-extrabold text-slate-900 mt-0.5">
                    {monitorValues?.etco2 || 36} <span className="text-xs font-normal text-slate-500">mmHg</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Capnography</div>
                </div>

                {/* Temperature */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-slate-400 text-[10px] font-semibold uppercase">Temperature</div>
                  <div className="text-lg font-extrabold text-slate-900 mt-0.5">
                    {monitorValues?.temperature || "37.1 °C"}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Core Body Temp</div>
                </div>
              </div>
            </section>
          </div>

          {/* Bottom Action Footer */}
          <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-end gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl border border-slate-300 bg-white hover:bg-slate-100 text-slate-700 font-semibold text-xs cursor-pointer transition-colors"
            >
              Close
            </button>

            <button
              onClick={() => onStartSimulation(selectedCase)}
              className="px-5 py-2.5 rounded-xl bg-teal-700 hover:bg-teal-800 text-white font-semibold text-xs cursor-pointer transition-all flex items-center gap-2 shadow-xs"
            >
              <Play className="w-4 h-4 fill-current text-white" />
              Start Simulation
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
