import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  // Same origin in dev: the browser only talks to Vite, which relays the API (and Django's
  // /media, /static) to Django. Target overridable with ONEA_API_URL (scripts/dev-up, e2e).
  server: {
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(
      ["/api", "/media", "/static"].map((prefix) => [
        prefix,
        { target: process.env.ONEA_API_URL ?? "http://127.0.0.1:8000", changeOrigin: false },
      ]),
    ),
  },
  build: {
    // dist/.vite/manifest.json : lu par scripts/verifier-budget-frontend.mjs (« npm run budget »).
    manifest: true,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: "react",
              test: /node_modules[\\/](react|react-dom|scheduler|react-router|react-router-dom)[\\/]/,
              priority: 30,
            },
            {
              name: "radix",
              test: /node_modules[\\/](radix-ui|@radix-ui|@floating-ui|aria-hidden|react-remove-scroll[^\\/]*|react-style-singleton|use-callback-ref|use-sidecar)[\\/]/,
              priority: 20,
            },
            { name: "tanstack", test: /node_modules[\\/]@tanstack[\\/]/, priority: 10 },
          ],
        },
      },
    },
  },
});
