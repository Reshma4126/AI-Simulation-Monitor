import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Volume2,
  RotateCcw,
  Play,
  AlertTriangle,
  ChevronDown,
  Users,
  ClipboardList,
  Sparkles,
  Award,
  BookOpen
} from "lucide-react";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import "../components/dashboard/dashboard.css";

const API = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export default function ScenarioStudioPage() {
  const navigate = useNavigate();

  // Navigation / Shell State
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [activeModal, setActiveModal] = useState(null);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);

  // Config State Options with Local Fallbacks
  const [levels, setLevels] = useState(["beginner", "intermediate", "advanced"]);
  const [locations, setLocations] = useState({
    ER: { label: "Emergency Room", icon: "🚨" },
    ICU: { label: "Intensive Care Unit", icon: "💉" },
    Theatre: { label: "Operating Theatre", icon: "😷" },
    Ward_Medical: { label: "Medical Ward", icon: "🏥" },
    Ward_Surgical: { label: "Surgical Ward", icon: "🏥" },
    Ward_Ortho: { label: "Orthopaedic Ward", icon: "🏥" },
    Ward_Neuro: { label: "Neurological Ward", icon: "🏥" },
    Ward_Cardio: { label: "Cardiology Ward", icon: "🏥" }
  });
  const [specialities, setSpecialities] = useState({
    ER: "Emergency Medicine",
    ICU: "Intensive Care",
    Anaesthesia: "Anaesthesia",
    Cardio: "Cardiology",
    Neuro: "Neurology",
    Trauma: "Trauma",
    Ortho: "Orthopaedics",
    Surgery: "General Surgery",
    Medicine: "General Medicine",
    Allied_Medical: "Allied Medical",
    Allied_Surgical: "Allied Surgical"
  });
  const [disciplines, setDisciplines] = useState({
    doctor: "Physician / Registrar",
    nurse: "Staff Nurse / Charge Nurse",
    physiotherapist: "Physiotherapist",
    allied: "Allied Health Professional"
  });

  // Instructor Selections
  const [selectedLevel, setSelectedLevel] = useState("beginner");
  const [selectedLocation, setSelectedLocation] = useState("ER");
  const [selectedSpeciality, setSelectedSpeciality] = useState("ER");
  const [selectedDisciplines, setSelectedDisciplines] = useState(["doctor"]);
  const [useOwnScenario, setUseOwnScenario] = useState(false);
  const [customText, setCustomText] = useState("");
  const [teamName, setTeamName] = useState("");

  // UI / Logic State
  const [spec, setSpec] = useState(null);
  const [loading, setLoading] = useState(false);
  const [narrating, setNarrating] = useState(false);
  const [showChecklist, setShowChecklist] = useState(false);

  // Load configuration options
  useEffect(() => {
    const token = sessionStorage.getItem("token");
    if (!token) {
      navigate("/");
      return;
    }

    fetch(`${API}/api/scenario/list`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load options");
        return res.json();
      })
      .then((data) => {
        if (data.levels) setLevels(data.levels);
        if (data.locations) setLocations(data.locations);
        if (data.specialities) setSpecialities(data.specialities);
        if (data.disciplines) setDisciplines(data.disciplines);
      })
      .catch((err) => {
        console.error("Error fetching scenario list:", err);
      });
  }, [navigate]);

  const handleGenerate = async () => {
    setLoading(true);
    setSpec(null);
    const token = sessionStorage.getItem("token");

    try {
      let resSpec;
      if (useOwnScenario) {
        // Parse custom instructor text first
        const res = await fetch(`${API}/api/scenario/instructor`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({ text: customText })
        });
        if (!res.ok) throw new Error("Failed to parse custom scenario");
        const parsedData = await res.json();
        resSpec = parsedData.spec;
      } else {
        // Standard generator
        const res = await fetch(`${API}/api/scenario/generate`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            level: selectedLevel,
            location: selectedLocation,
            discipline: selectedDisciplines,
            speciality: selectedSpeciality
          })
        });
        if (!res.ok) throw new Error("Failed to generate scenario");
        const genData = await res.json();
        resSpec = genData.spec;
      }

      setSpec(resSpec);
    } catch (err) {
      console.error(err);
      alert("Error generating scenario. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleLaunch = async () => {
    if (!spec) return;
    const token = sessionStorage.getItem("token");
    let sessionCode = sessionStorage.getItem("session_code");

    if (!sessionCode) {
      try {
        const initRes = await fetch(`${API}/session/create`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
        const initData = await initRes.json();
        sessionCode = initData.session_code;
        sessionStorage.setItem("session_code", sessionCode);
      } catch (err) {
        console.error("Failed to create session code on the fly:", err);
        alert("Failed to create a session. Please return to the Dashboard first.");
        return;
      }
    }

    try {
      const res = await fetch(`${API}/api/scenario/start`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          spec: spec,
          session_code: sessionCode
        })
      });

      if (!res.ok) throw new Error("Failed to launch scenario telemetry");
      
      // Save team name in sessionStorage for reporting
      sessionStorage.setItem("team_name", teamName || "Resus Team");
      
      // Redirect to initializing screen
      navigate("/initializing");
    } catch (err) {
      console.error(err);
      alert("Error launching scenario. Please try again.");
    }
  };

  const handleNarrate = () => {
    if (!spec || narrating) return;
    setNarrating(true);
    const token = sessionStorage.getItem("token");

    fetch(`${API}/api/scenario/narrate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ spec })
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.text) {
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance(data.text);
          utterance.onend = () => setNarrating(false);
          utterance.onerror = () => setNarrating(false);
          window.speechSynthesis.speak(utterance);
        } else {
          setNarrating(false);
        }
      })
      .catch((err) => {
        console.error(err);
        setNarrating(false);
      });
  };

  const handleToggleDiscipline = (discKey) => {
    setSelectedDisciplines((prev) =>
      prev.includes(discKey)
        ? prev.filter((d) => d !== discKey)
        : [...prev, discKey]
    );
  };

  const handleLogout = () => {
    sessionStorage.clear();
    navigate("/");
  };

  return (
    <div className="medsim-dashboard-page" style={{ backgroundColor: "#F8FAFC" }}>
      {/* Navbar */}
      <Navbar
        searchQuery=""
        setSearchQuery={() => {}}
        showNotifications={showNotifications}
        setShowNotifications={setShowNotifications}
        showProfileMenu={showProfileMenu}
        setShowProfileMenu={setShowProfileMenu}
        handleStartSimulation={() => navigate("/initializing")}
        handleLogout={handleLogout}
        onOpenSettings={() => setActiveModal("settings")}
      />

      <div style={{ display: "flex", flex: 1, overflow: "hidden", position: "relative" }}>
        {/* Sidebar */}
        <Sidebar
          sidebarExpanded={sidebarExpanded}
          setSidebarExpanded={setSidebarExpanded}
          activeTab="simulation"
          setActiveTab={() => {}}
          handleStartSimulation={() => navigate("/initializing")}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        {/* Scrollable Main Content */}
        <main className="medsim-main-content" style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: "24px", padding: "32px 40px", overflowY: "auto" }}>
          
          {/* Left Configuration Panel */}
          <div style={{
            backgroundColor: "#FFFFFF",
            border: "1px solid #E2E8F0",
            borderRadius: "16px",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
            boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
            height: "fit-content"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", paddingBottom: "12px", borderBottom: "1px solid #F1F5F9" }}>
              <div style={{
                width: "36px", height: "36px", borderRadius: "10px",
                backgroundColor: "#F0FDFA", border: "1px solid #CCFBF1",
                display: "flex", alignItems: "center", justifyContent: "center",
                color: "#0F766E"
              }}>
                <Sparkles size={18} />
              </div>
              <div>
                <h2 style={{ fontSize: "16px", fontWeight: 700, color: "#0F172A", margin: 0 }}>Scenario Studio</h2>
                <p style={{ fontSize: "11px", color: "#64748B", margin: 0 }}>Design your simulation parameters</p>
              </div>
            </div>
            
            {/* Difficulty Level */}
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Difficulty Level</label>
              <div style={{ display: "flex", gap: "10px" }}>
                {levels.map((lvl) => {
                  const active = selectedLevel === lvl;
                  const labelMap = { beginner: "Beg", intermediate: "Int", advanced: "Adv" };
                  const colorMap = { beginner: "#0F766E", intermediate: "#D97706", advanced: "#DC2626" };
                  return (
                    <button
                      key={lvl}
                      onClick={() => setSelectedLevel(lvl)}
                      style={{
                        flex: 1,
                        padding: "10px 6px",
                        borderRadius: "10px",
                        border: active ? `2px solid ${colorMap[lvl]}` : "1px solid #E2E8F0",
                        background: active ? `${colorMap[lvl]}0A` : "#FFFFFF",
                        color: active ? colorMap[lvl] : "#64748B",
                        fontWeight: 600,
                        fontSize: "12px",
                        cursor: "pointer",
                        textTransform: "capitalize",
                        transition: "all 0.2s"
                      }}
                    >
                      {labelMap[lvl] || lvl}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Department Location */}
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Location / Department</label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                {Object.entries(locations).map(([key, loc]) => {
                  const active = selectedLocation === key;
                  return (
                    <button
                      key={key}
                      onClick={() => setSelectedLocation(key)}
                      style={{
                        padding: "10px 8px",
                        borderRadius: "10px",
                        border: active ? "2px solid #0F766E" : "1px solid #E2E8F0",
                        background: active ? "#F0FDFA" : "#FFFFFF",
                        color: active ? "#0F766E" : "#64748B",
                        fontSize: "12px",
                        fontWeight: 500,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        transition: "all 0.2s",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis"
                      }}
                    >
                      <span>{loc.icon || "🏥"}</span>
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{loc.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Speciality Dropdown */}
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Speciality</label>
              <div style={{ position: "relative" }}>
                <select
                  value={selectedSpeciality}
                  onChange={(e) => setSelectedSpeciality(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: "10px",
                    border: "1px solid #E2E8F0",
                    background: "#FFFFFF",
                    color: "#0F172A",
                    fontSize: "13px",
                    outline: "none",
                    cursor: "pointer",
                    appearance: "none"
                  }}
                >
                  {Object.entries(specialities).map(([key, label]) => (
                    <option key={key} value={key} style={{ color: "#0F172A" }}>
                      {label}
                    </option>
                  ))}
                </select>
                <ChevronDown size={16} color="#64748B" style={{ position: "absolute", right: "12px", top: "13px", pointerEvents: "none" }} />
              </div>
            </div>

            {/* Disciplines Selection */}
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Speciality Disciplines</label>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {Object.entries(disciplines).map(([key, label]) => {
                  const active = selectedDisciplines.includes(key);
                  return (
                    <div
                      key={key}
                      onClick={() => handleToggleDiscipline(key)}
                      style={{
                        padding: "8px 12px",
                        borderRadius: "10px",
                        border: "1px solid #E2E8F0",
                        background: active ? "#F0FDFA" : "#FFFFFF",
                        color: active ? "#0F766E" : "#64748B",
                        fontSize: "12px",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        transition: "all 0.2s"
                      }}
                    >
                      <span style={{ fontWeight: active ? 600 : 500 }}>{label}</span>
                      <input
                        type="checkbox"
                        checked={active}
                        readOnly
                        style={{ accentColor: "#0F766E", width: "14px", height: "14px", cursor: "pointer" }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Use own scenario Toggle */}
            <div style={{ borderTop: "1px solid #F1F5F9", paddingTop: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContext: "space-between", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ fontSize: "12px", fontWeight: 600, color: "#64748B" }}>Use My Own Scenario</span>
                <label className="switch" style={{ position: "relative", display: "inline-block", width: "36px", height: "20px" }}>
                  <input
                    type="checkbox"
                    checked={useOwnScenario}
                    onChange={(e) => setUseOwnScenario(e.target.checked)}
                    style={{ opacity: 0, width: 0, height: 0 }}
                  />
                  <span style={{
                    position: "absolute",
                    cursor: "pointer",
                    top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: useOwnScenario ? "#0F766E" : "#CBD5E1",
                    transition: ".3s",
                    borderRadius: "20px"
                  }}>
                    <span style={{
                      position: "absolute",
                      content: "",
                      height: "14px", width: "14px",
                      left: useOwnScenario ? "18px" : "3px",
                      bottom: "3px",
                      backgroundColor: "white",
                      transition: ".3s",
                      borderRadius: "50%"
                    }} />
                  </span>
                </label>
              </div>

              {useOwnScenario && (
                <textarea
                  placeholder="Describe your custom clinical scenario. AI will parse rhythm, checklist and demographics..."
                  value={customText}
                  onChange={(e) => setCustomText(e.target.value)}
                  style={{
                    width: "100%",
                    height: "80px",
                    padding: "10px",
                    borderRadius: "10px",
                    border: "1px solid #E2E8F0",
                    background: "#F8FAFC",
                    color: "#0F172A",
                    fontSize: "12px",
                    outline: "none",
                    resize: "none"
                  }}
                />
              )}
            </div>

            {/* Team details */}
            <div style={{ borderTop: "1px solid #F1F5F9", paddingTop: "16px" }}>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Team Name</label>
              <input
                type="text"
                placeholder="e.g. ER Resus Team"
                value={teamName}
                onChange={(e) => setTeamName(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: "10px",
                  border: "1px solid #E2E8F0",
                  background: "#F8FAFC",
                  color: "#0F172A",
                  fontSize: "13px",
                  outline: "none"
                }}
              />
            </div>

            {/* Generate Action Button */}
            <button
              onClick={handleGenerate}
              disabled={loading || (useOwnScenario && !customText.trim())}
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: "12px",
                border: "none",
                background: "linear-gradient(135deg, #0F766E, #0D9488)",
                color: "#FFFFFF",
                fontWeight: 700,
                fontSize: "13px",
                cursor: "pointer",
                boxShadow: "0 2px 6px rgba(15, 118, 110, 0.2)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                transition: "all 0.2s"
              }}
            >
              {loading ? "Generating..." : "Generate Scenario"}
            </button>
          </div>

          {/* Right Preview Panel */}
          <div style={{
            backgroundColor: "#FFFFFF",
            border: "1px solid #E2E8F0",
            borderRadius: "16px",
            padding: "32px",
            boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
            display: "flex",
            flexDirection: "column",
            justifyContent: spec ? "flex-start" : "center",
            alignItems: spec ? "stretch" : "center",
            minHeight: "560px"
          }}>
            {!spec ? (
              <div style={{ textAlign: "center", maxWidth: "440px" }}>
                <div style={{
                  width: "72px",
                  height: "72px",
                  borderRadius: "50%",
                  background: "#F0FDFA",
                  border: "1px solid #CCFBF1",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 20px"
                }}>
                  <Activity size={32} color="#0F766E" />
                </div>
                <h3 style={{ fontSize: "20px", fontWeight: 700, color: "#0F172A", marginBottom: "8px" }}>Scenario Studio</h3>
                <p style={{ fontSize: "13px", color: "#64748B", lineHeight: 1.6 }}>
                  Configure your scenario parameters on the left and click **Generate Scenario** to begin your simulation training.
                </p>
              </div>
            ) : (
              // Generated Scenario Specification Layout
              <div style={{ animation: "reveal 0.4s ease-out" }}>
                {/* Header Info */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px" }}>
                  <div>
                    <span style={{
                      fontSize: "10px",
                      fontWeight: 700,
                      color: "#0F766E",
                      background: "#F0FDFA",
                      border: "1px solid #CCFBF1",
                      padding: "4px 8px",
                      borderRadius: "6px",
                      textTransform: "uppercase",
                      letterSpacing: "0.5px"
                    }}>{spec.location_label || spec.location}</span>
                    <h2 style={{ fontSize: "24px", fontWeight: 800, color: "#0F172A", marginTop: "10px", marginBottom: "4px" }}>
                      {spec.title}
                    </h2>
                    <p style={{ fontSize: "13px", color: "#64748B", margin: 0, fontStyle: "italic" }}>
                      {spec.patient?.presentation}
                    </p>
                  </div>
                  <span style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    color: spec.level === "advanced" ? "#DC2626" : spec.level === "intermediate" ? "#D97706" : "#0F766E",
                    background: spec.level === "advanced" ? "#FEE2E2" : spec.level === "intermediate" ? "#FEF3C7" : "#F0FDFA",
                    border: spec.level === "advanced" ? "1px solid #FCA5A5" : spec.level === "intermediate" ? "1px solid #FCD34D" : "1px solid #CCFBF1",
                    padding: "6px 12px",
                    borderRadius: "20px",
                    textTransform: "uppercase",
                    letterSpacing: "0.5px"
                  }}>{spec.level}</span>
                </div>

                {/* Patient Demographics Card */}
                <div style={{
                  background: "#F8FAFC",
                  border: "1px solid #E2E8F0",
                  borderRadius: "14px",
                  padding: "16px 20px",
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  gap: "16px",
                  marginBottom: "24px"
                }}>
                  <div>
                    <span style={{ display: "block", fontSize: "11px", color: "#64748B", marginBottom: "4px" }}>Age</span>
                    <span style={{ fontSize: "18px", fontWeight: 700, color: "#0F172A" }}>{spec.patient?.age} Years</span>
                  </div>
                  <div>
                    <span style={{ display: "block", fontSize: "11px", color: "#64748B", marginBottom: "4px" }}>Sex</span>
                    <span style={{ fontSize: "18px", fontWeight: 700, color: "#0F172A" }}>{spec.patient?.sex}</span>
                  </div>
                  <div>
                    <span style={{ display: "block", fontSize: "11px", color: "#64748B", marginBottom: "4px" }}>Weight</span>
                    <span style={{ fontSize: "18px", fontWeight: 700, color: "#0F172A" }}>{spec.patient?.weight_kg} kg</span>
                  </div>
                </div>

                {/* Clinical History */}
                <div style={{ marginBottom: "24px" }}>
                  <h4 style={{ fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Patient History</h4>
                  <p style={{ fontSize: "13px", color: "#334155", lineHeight: 1.5, background: "#F8FAFC", padding: "12px 16px", borderRadius: "10px", borderLeft: "3px solid #0F766E", margin: 0 }}>
                    {spec.patient?.history}
                  </p>
                </div>

                {/* Complications & Hints */}
                {((spec.complications && spec.complications.length > 0) || (spec.hints && spec.hints.length > 0)) && (
                  <div style={{ display: "grid", gridTemplateColumns: spec.complications?.length && spec.hints?.length ? "1fr 1fr" : "1fr", gap: "20px", marginBottom: "24px" }}>
                    {spec.complications?.length > 0 && (
                      <div>
                        <h4 style={{ fontSize: "11px", fontWeight: 600, color: "#DC2626", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                          <AlertTriangle size={14} /> Complications
                        </h4>
                        <ul style={{ paddingLeft: "16px", margin: 0, color: "#475569", fontSize: "12px", lineHeight: 1.5 }}>
                          {spec.complications.map((comp, idx) => <li key={idx} style={{ marginBottom: "4px" }}>{comp}</li>)}
                        </ul>
                      </div>
                    )}
                    {spec.hints?.length > 0 && (
                      <div>
                        <h4 style={{ fontSize: "11px", fontWeight: 600, color: "#16A34A", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Helpful Hints</h4>
                        <ul style={{ paddingLeft: "16px", margin: 0, color: "#475569", fontSize: "12px", lineHeight: 1.5 }}>
                          {spec.hints.map((hint, idx) => <li key={idx} style={{ marginBottom: "4px" }}>{hint}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Resources Profile */}
                <div style={{ marginBottom: "24px" }}>
                  <h4 style={{ fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Resources Available</h4>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                    {Object.entries(spec.resources || {}).map(([key, val]) => {
                      if (typeof val !== "boolean") return null;
                      const labelMap = {
                        crash_cart: "Crash Cart",
                        defibrillator: "Defibrillator",
                        ventilator: "Ventilator",
                        advanced_airway: "Advanced Airway",
                        iv_access_ready: "IV Access"
                      };
                      return (
                        <span key={key} style={{
                          fontSize: "11px",
                          fontWeight: 500,
                          color: val ? "#16A34A" : "#DC2626",
                          background: val ? "#F0FDF4" : "#FEE2E2",
                          border: val ? "1px solid #BBF7D0" : "1px solid #FCA5A5",
                          padding: "6px 12px",
                          borderRadius: "8px",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px"
                        }}>
                          {val ? "✓" : "✗"} {labelMap[key] || key}
                        </span>
                      );
                    })}
                  </div>
                </div>

                {/* Gamification Panel */}
                <div style={{
                  background: "linear-gradient(135deg, #F0FDFA, #F8FAFC)",
                  border: "1px solid #CCFBF1",
                  borderRadius: "14px",
                  padding: "16px 20px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "24px"
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <Users size={20} color="#0F766E" />
                    <div>
                      <span style={{ display: "block", fontSize: "10px", color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px" }}>Target Team Size</span>
                      <span style={{ fontSize: "14px", fontWeight: 700, color: "#0F172A" }}>{spec.team_size} Members</span>
                    </div>
                  </div>
                  <div>
                    <span style={{ display: "block", fontSize: "10px", color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", textAlign: "right" }}>XP Reward</span>
                    <span style={{ fontSize: "16px", fontWeight: 700, color: "#0F766E" }}>+{spec.xp_reward} XP</span>
                  </div>
                </div>

                {/* Expected Action Checklist Accordion */}
                <div style={{ marginBottom: "28px", border: "1px solid #E2E8F0", borderRadius: "10px" }}>
                  <button
                    onClick={() => setShowChecklist(!showChecklist)}
                    style={{
                      width: "100%",
                      padding: "12px 16px",
                      background: "#F8FAFC",
                      border: "none",
                      color: "#0F172A",
                      fontSize: "13px",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      borderRadius: showChecklist ? "10px 10px 0 0" : "10px"
                    }}
                  >
                    <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <ClipboardList size={16} color="#0F766E" />
                      Expected Action Checklist
                    </span>
                    <span>{showChecklist ? "▲" : "▼"}</span>
                  </button>

                  {showChecklist && (
                    <div style={{ padding: "12px 16px", background: "#FFFFFF", borderTop: "1px solid #E2E8F0" }}>
                      {spec.checklist?.map((item, idx) => (
                        <div key={idx} style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "8px 0",
                          borderBottom: idx < spec.checklist.length - 1 ? "1px solid #F1F5F9" : "none",
                          fontSize: "12px",
                          color: "#334155"
                        }}>
                          <span style={{ display: "flex", alignItems: "center", gap: "6px", color: item.critical ? "#DC2626" : "#334155", fontWeight: item.critical ? 600 : 400 }}>
                            {item.critical ? "★" : "○"} {item.action}
                          </span>
                          <span style={{ fontSize: "11px", background: "#F1F5F9", padding: "2px 6px", borderRadius: "4px", color: "#64748B" }}>
                            &lt; {item.window_sec}s
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Simulation Action Buttons */}
                <div style={{ display: "flex", gap: "16px" }}>
                  <button
                    onClick={handleLaunch}
                    style={{
                      flex: 1,
                      padding: "14px",
                      borderRadius: "12px",
                      border: "none",
                      background: "linear-gradient(135deg, #16A34A, #15803D)",
                      color: "#ffffff",
                      fontWeight: 700,
                      fontSize: "14px",
                      cursor: "pointer",
                      boxShadow: "0 2px 6px rgba(22, 163, 74, 0.2)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "8px"
                    }}
                  >
                    <Play size={16} fill="currentColor" /> Launch Scenario
                  </button>

                  <button
                    onClick={handleNarrate}
                    disabled={narrating}
                    style={{
                      padding: "14px 20px",
                      borderRadius: "12px",
                      border: "1px solid #E2E8F0",
                      background: narrating ? "#F1F5F9" : "#FFFFFF",
                      color: "#0F766E",
                      fontWeight: 600,
                      fontSize: "13px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px"
                    }}
                  >
                    <Volume2 size={16} /> {narrating ? "Narrating..." : "Narrate Intro"}
                  </button>

                  <button
                    onClick={handleGenerate}
                    style={{
                      padding: "14px 20px",
                      borderRadius: "12px",
                      border: "1px solid #E2E8F0",
                      background: "#FFFFFF",
                      color: "#64748B",
                      fontWeight: 600,
                      fontSize: "13px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px"
                    }}
                  >
                    <RotateCcw size={16} /> Regenerate
                  </button>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Global settings or other modals */}
      <DashboardModals
        activeModal={activeModal}
        onClose={() => setActiveModal(null)}
        handleStartSimulation={() => navigate("/initializing")}
        initialSessions={[]}
      />
    </div>
  );
}
