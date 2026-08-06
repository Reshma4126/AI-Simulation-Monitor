import { io } from "socket.io-client";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "https://imsr2-a3xs.onrender.com";

const socket = io(BACKEND_URL, {
  autoConnect: false,
  transports: ["websocket", "polling"],
  reconnection: true,
  reconnectionAttempts: Infinity,
  reconnectionDelay: 1000,
});

socket.on("connect", () => {
  console.log("[Socket] Connected:", socket.id);

  // Auto-rejoin session on reconnect (e.g. after backend restart)
  const token = sessionStorage.getItem("token");
  const sessionCode = sessionStorage.getItem("session_code");
  if (token && sessionCode) {
    console.log("[Socket] Auto-rejoining session:", sessionCode);
    socket.emit("join_session", { session_code: sessionCode, token });
  }
});

socket.on("join_confirmed", (data) => {
  console.log("[Socket] Join confirmed for session:", data.session_code, "role:", data.role);
});

socket.on("disconnect", (reason) => {
  console.log("[Socket] Disconnected:", reason);
});

socket.on("connect_error", (err) => {
  console.error("[Socket] Connection error:", err.message);
});

export default socket;
