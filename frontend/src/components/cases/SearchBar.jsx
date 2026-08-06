import React from "react";
import { Search } from "lucide-react";
import "../dashboard/dashboard.css";

export default function SearchBar({ searchQuery, setSearchQuery }) {
  return (
    <div className="medsim-search-container" style={{ maxWidth: "100%", margin: 0 }}>
      <Search className="medsim-search-icon" size={18} />
      <input
        type="text"
        placeholder="Search by patient, diagnosis or scenario..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="medsim-search-input"
        style={{ height: "46px", borderRadius: "12px" }}
      />
    </div>
  );
}
