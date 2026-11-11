import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Content-Security-Policy is injected only into production builds (the dev server needs inline scripts).
const csp = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src https://fonts.gstatic.com",
  "img-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const cspPlugin = (): Plugin => ({
  name: "huqooq-csp",
  apply: "build",
  transformIndexHtml: (html) =>
    html.replace("<head>", `<head>\n    <meta http-equiv="Content-Security-Policy" content="${csp}" />`),
});

// In dev, /api/* is proxied to the FastAPI server, so the frontend never needs CORS or an absolute URL.
export default defineConfig({
  plugins: [react(), cspPlugin()],
  server: {
    port: 5173,
    // Match Uvicorn's explicit IPv4 bind on Windows; `localhost` may resolve to ::1.
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
