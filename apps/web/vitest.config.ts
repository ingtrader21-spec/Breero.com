import { defineConfig } from "vitest/config";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } },
  test: { environment: "jsdom", setupFiles: ["./vitest.setup.ts"], exclude: ["tests/e2e/**", "tests/fullstack/**", "node_modules/**", ".next/**"] },
});
