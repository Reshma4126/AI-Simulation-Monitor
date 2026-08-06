import React from "react";

export default function CaseFilter({ activeFilter, setActiveFilter, favoritesCount }) {
  const filters = [
    { id: "All", label: "All Cases" },
    { id: "Favorites", label: `Favorites (${favoritesCount})` },
    { id: "ACLS", label: "ACLS" },
    { id: "PALS", label: "PALS" },
    { id: "Emergency", label: "Emergency" },
    { id: "Cardiology", label: "Cardiology" },
    { id: "Respiratory", label: "Respiratory" },
    { id: "Trauma", label: "Trauma" },
  ];

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
      {filters.map((filter) => {
        const isActive = activeFilter === filter.id;
        return (
          <button
            key={filter.id}
            onClick={() => setActiveFilter(filter.id)}
            className={`px-4 py-2 rounded-xl text-xs font-semibold whitespace-nowrap cursor-pointer transition-all ${
              isActive
                ? "bg-teal-700 text-white shadow-xs"
                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50 hover:text-slate-900"
            }`}
          >
            {filter.label}
          </button>
        );
      })}
    </div>
  );
}
