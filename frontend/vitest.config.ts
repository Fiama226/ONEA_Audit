import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Fuseau local volontairement différent d'Africa/Ouagadougou pour détecter un formatage naïf.
process.env.TZ = "Europe/Paris";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    env: { VITE_API_URL: "http://localhost:8000" },
    exclude: ["node_modules", "dist", "e2e/**"],
    coverage: {
      provider: "v8",
      include: ["src/**"],
      exclude: ["src/api/schema.d.ts", "src/test/**", "**/*.test.*"],
    },
  },
});
