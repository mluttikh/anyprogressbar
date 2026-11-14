import { defineConfig } from "vitest/config";

// unit tests only; the browser tests (test/browser) run with Playwright
export default defineConfig({ test: { include: ["test/*.test.ts"] } });
