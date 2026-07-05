import { defineConfig } from "vitest/config";

// Separate from vite.config.ts (which configures the dev server / WSL proxy) --
// tests are pure functions, so a plain node environment is enough; no jsdom.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
