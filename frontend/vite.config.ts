import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The backend runs on this port (see README). In development, Vite forwards
// /api to it, so the browser talks to a single origin and no CORS is needed.
const API_URL = "http://127.0.0.1:8100";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5180,
    strictPort: true,
    proxy: { "/api": API_URL },
  },
  test: {
    environment: "jsdom",
    // One jsdom per worker instead of one per file: the environment was half
    // the time of the suite (25 files, 25 environments).
    pool: "vmThreads",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
    unstubGlobals: true,
  },
});
