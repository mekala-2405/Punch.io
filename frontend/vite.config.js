import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy sends /api to the local Q&A backend when self-hosting.
// On Cloudflare Pages the same /api path is served by functions/api/ask.js.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
