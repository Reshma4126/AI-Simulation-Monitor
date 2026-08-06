import React from "react";
import { Heart, ChevronRight, User } from "lucide-react";
import { PatientBadge, DifficultyBadge } from "./PatientBadge";

export default function CaseCard({ caseItem, onSelectCase, onToggleFavorite }) {
  // Initials for avatar
  const getInitials = (name) => {
    if (!name) return "PT";
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .substring(0, 2)
      .toUpperCase();
  };

  return (
    <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:-translate-y-1 hover:border-slate-300 hover:shadow-md transition-all duration-200 flex flex-col justify-between h-full group">
      <div>
        {/* Top Bar: Avatar & Category + Favorite Button */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-teal-50 border border-teal-200 text-teal-700 font-bold text-xs flex items-center justify-center shrink-0">
              {getInitials(caseItem.patientName)}
            </div>
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-teal-700 bg-teal-50 border border-teal-200 px-2 py-0.5 rounded-md">
                {caseItem.category}
              </span>
            </div>
          </div>

          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleFavorite(caseItem.id);
            }}
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-500 cursor-pointer transition-colors"
            title={caseItem.isFavorite ? "Remove from favorites" : "Add to favorites"}
          >
            <Heart
              className={`w-4.5 h-4.5 ${
                caseItem.isFavorite ? "fill-rose-500 text-rose-500" : "text-slate-400"
              }`}
            />
          </button>
        </div>

        {/* Patient Name & Age / Gender */}
        <div className="mb-3">
          <h3 className="text-base font-bold text-slate-900 group-hover:text-teal-700 transition-colors">
            {caseItem.patientName}
          </h3>
          <div className="mt-1">
            <PatientBadge age={`${caseItem.age} Yrs`} gender={caseItem.gender} />
          </div>
        </div>

        {/* Diagnosis & Chief Complaint */}
        <div className="space-y-2 mb-4 text-xs">
          <div>
            <span className="text-slate-400 font-medium block text-[11px] uppercase tracking-wide">
              Diagnosis
            </span>
            <span className="font-bold text-slate-800 text-sm">
              {caseItem.diagnosis}
            </span>
          </div>

          <div>
            <span className="text-slate-400 font-medium block text-[11px] uppercase tracking-wide">
              Chief Complaint
            </span>
            <span className="text-slate-600 line-clamp-2 leading-relaxed">
              {caseItem.chiefComplaint}
            </span>
          </div>
        </div>
      </div>

      {/* Footer: Difficulty Badge & View Case Button */}
      <div className="pt-3 border-t border-slate-100 flex items-center justify-between mt-2">
        <div>
          <span className="text-[10px] text-slate-400 font-medium block uppercase tracking-wide">
            Difficulty
          </span>
          <DifficultyBadge difficulty={caseItem.difficulty} />
        </div>

        <button
          onClick={() => onSelectCase(caseItem)}
          className="bg-slate-50 hover:bg-teal-700 text-slate-700 hover:text-white border border-slate-200 hover:border-teal-700 rounded-xl px-3.5 py-1.5 text-xs font-semibold cursor-pointer transition-all flex items-center gap-1"
        >
          View Case
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
