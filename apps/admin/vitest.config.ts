import { defineConfig } from "vitest/config";

// Node environment: components are rendered with react-dom/server, so no DOM shim is needed.
export default defineConfig({
  esbuild: { jsx: "automatic" },
  test: { environment: "node", include: ["tests/**/*.test.{ts,tsx}"], exclude: ["node_modules/**", ".next/**"] },
});
