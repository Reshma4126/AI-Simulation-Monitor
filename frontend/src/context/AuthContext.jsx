import React, { createContext, useContext, useState, useEffect } from "react";

const API = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const getStoredToken = () => {
    return sessionStorage.getItem("token") || localStorage.getItem("token");
  };

  const setAuthStorage = (token, role, username, rememberMe) => {
    const storage = rememberMe ? localStorage : sessionStorage;
    storage.setItem("token", token);
    storage.setItem("role", role);
    storage.setItem("username", username);
  };

  const clearAuthStorage = () => {
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("role");
    sessionStorage.removeItem("username");
    sessionStorage.removeItem("session_code");
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("username");
  };

  const checkAuth = async () => {
    const storedToken = getStoredToken();
    const headers = {};
    if (storedToken && storedToken !== "demo-token") {
      headers["Authorization"] = `Bearer ${storedToken}`;
    }

    try {
      const res = await fetch(`${API}/auth/me`, {
        method: "GET",
        headers,
        credentials: "include",
      });

      if (res.ok) {
        const userData = await res.json();
        setUser(userData);
      } else {
        clearAuthStorage();
        setUser(null);
      }
    } catch (err) {
      console.warn("Session check failed:", err);
      clearAuthStorage();
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  const login = async (username, password, role, rememberMe = false) => {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username, password, role, remember_me: rememberMe }),
    });

    if (!res.ok) {
      let errMsg = "Invalid username, password, or role.";
      try {
        const data = await res.json();
        if (data.detail) errMsg = data.detail;
      } catch (e) {}
      throw new Error(errMsg);
    }

    const data = await res.json();
    if (!data.access_token || data.access_token === "demo-token") {
      throw new Error("Invalid access token returned from server.");
    }

    setAuthStorage(data.access_token, data.role, username, rememberMe);
    if (data.session_code) {
      sessionStorage.setItem("session_code", data.session_code);
    }

    const authenticatedUser = data.user || { username, role: data.role, id: 1 };
    setUser(authenticatedUser);

    return {
      user: authenticatedUser,
      role: data.role,
      token: data.access_token,
      session_code: data.session_code,
    };
  };

  const logout = async () => {
    try {
      await fetch(`${API}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch (err) {
      console.warn("Logout request failed:", err);
    } finally {
      clearAuthStorage();
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        role: user?.role || null,
        isAuthenticated: !!user,
        loading,
        login,
        logout,
        checkAuth,
        getStoredToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
