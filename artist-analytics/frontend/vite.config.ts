import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api goes to the FastAPI server. In Docker, nginx does the same job.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
