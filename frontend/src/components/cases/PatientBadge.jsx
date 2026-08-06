import React from "react";

export function PatientBadge({ age, gender }) {
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
      {age} • {gender}
    </span>
  );
}

export function DifficultyBadge({ difficulty }) {
  const getColors = () => {
    switch (difficulty) {
      case "Beginner":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "Intermediate":
        return "bg-teal-50 text-teal-700 border-teal-200";
      case "Advanced":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "Critical":
        return "bg-rose-50 text-rose-700 border-rose-200";
      default:
        return "bg-slate-50 text-slate-700 border-slate-200";
    }
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getColors()}`}>
      {difficulty}
    </span>
  );
}
