import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      "/auth": "https://imsr2-a3xs.onrender.com/",
      "/session": "https://imsr2-a3xs.onrender.com/",
      "/meta": "https://imsr2-a3xs.onrender.com/",
      "/socket.io": {
        target: "https://imsr2-a3xs.onrender.com/",
        ws: true,
      },
    },
  },
});
