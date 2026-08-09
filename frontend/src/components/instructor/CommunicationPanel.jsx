import { useState, useEffect, useRef } from "react";
import socket from "../../socket";

const API = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function CommunicationPanel({ sessionCode }) {
  const [activeTab, setActiveTab] = useState("events");
  const [events, setEvents] = useState([]);
  const [chatInput, setChatInput] = useState("");
  
  const eventEndRef = useRef(null);

  // Fetch past event log history on load
  useEffect(() => {
    if (!sessionCode) return;
    const token = sessionStorage.getItem("token");
    fetch(`${API}/session/${sessionCode}/log`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.event_log)) {
          setEvents(data.event_log);
        }
      })
      .catch((err) => console.error("[CommunicationPanel] Fetch log error:", err));
  }, [sessionCode]);

  useEffect(() => {
    const handleEvent = (entry) => {
      setEvents((prev) => {
        if (prev.some((e) => e.timestamp === entry.timestamp && e.event === entry.event)) {
          return prev;
        }
        const updated = [...prev, entry];
        if (updated.length > 50) return updated.slice(updated.length - 50);
        return updated;
      });
      setTimeout(() => eventEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    };

    const handleHistoryLog = (data) => {
      if (data && Array.isArray(data.event_log)) {
        setEvents(data.event_log);
      }
    };

    socket.on("session_event", handleEvent);
    socket.on("session_history_log", handleHistoryLog);
    return () => {
      socket.off("session_event", handleEvent);
      socket.off("session_history_log", handleHistoryLog);
    };
  }, []);

  const handleSendChat = () => {
    if (!chatInput.trim()) return;
    const text = chatInput.trim();
    
    socket.emit("add_event_log", {
      session_code: sessionCode,
      event: `Instructor Comment: ${text}`,
    });
    
    socket.emit("faculty_comment", {
      session_code: sessionCode,
      comment: text,
      from: "Instructor",
      timestamp: Date.now()
    });
    
    setChatInput("");
  };

  return (
    <div className="communication-footer">
      <div className="comm-footer-tabs">
        <button 
          className={`comm-tab ${activeTab === "events" ? "active" : ""}`}
          onClick={() => setActiveTab("events")}
        >
          Event Log ({events.length})
        </button>
        <button 
          className={`comm-tab ${activeTab === "chat" ? "active" : ""}`}
          onClick={() => setActiveTab("chat")}
        >
          Instructor Chat
        </button>
      </div>

      <div className="comm-footer-content">
        {activeTab === "events" && (
          <div className="comm-pane event-list compact-list">
            {events.length === 0 && <div className="empty-state">No recent events.</div>}
            {events.map((e, i) => (
              <div key={i} className="event-entry compact">
                <span className="event-time">
                  {new Date(e.timestamp).toLocaleTimeString()}
                </span>
                <span className="event-text">{e.event}</span>
              </div>
            ))}
            <div ref={eventEndRef} />
          </div>
        )}

        {activeTab === "chat" && (
          <div className="comm-pane chat-pane compact-chat">
            <div className="chat-input-area">
              <input 
                type="text" 
                value={chatInput} 
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendChat()}
                placeholder="Broadcast message to students..." 
              />
              <button className="btn-classic btn-sm" onClick={handleSendChat}>Send</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
