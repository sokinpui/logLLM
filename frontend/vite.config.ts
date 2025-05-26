// --- Create file: frontend/vite.config.ts ---
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173, // Your current port
    strictPort: true, // Fails if port is in use
  },
});
