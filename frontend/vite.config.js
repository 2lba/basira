import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy backend paths through the same origin as the frontend so OAuth
// session cookies don't get split between origins (the bug we hit when
// localhost:5173 and ngrok.dev were separate origins).
const BACKEND = process.env.VITE_BACKEND_INTERNAL_URL || "http://backend:8000";
const PROXY_PATHS = [
  "/auth",
  "/api",
  "/webhooks",
  "/share",
  "/test",
  "/healthz",
  "/readyz",
];

const proxy = Object.fromEntries(
  PROXY_PATHS.map((p) => [
    p,
    {
      target: BACKEND,
      changeOrigin: true,
      secure: false,
      ws: false,
    },
  ]),
);

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    proxy,
    hmr: {
      clientPort: process.env.VITE_PUBLIC_HMR_PORT
        ? Number(process.env.VITE_PUBLIC_HMR_PORT)
        : undefined,
      host: process.env.VITE_PUBLIC_HMR_HOST || undefined,
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 5173,
  },
});
