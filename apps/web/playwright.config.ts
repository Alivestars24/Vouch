import { defineConfig, devices } from "@playwright/test";

const authenticated = process.env.VOUCH_E2E_AUTH === "supabase";
const decoded = process.env.VOUCH_E2E_MEDIA === "decoded";
if (decoded && !authenticated) throw new Error("Decoded browser proof requires local Supabase Auth.");

export default defineConfig({
  testDir: "./e2e",
  testMatch: decoded ? "decoded-media.spec.ts" : authenticated ? ["authenticated.spec.ts", "design.spec.ts"] : "workflow.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    // Auth traces would persist passwords/JWTs; never record that transport.
    trace: authenticated ? "off" : "retain-on-failure",
  },
  webServer: {
    command: authenticated ? "npm run dev:authenticated" : "npm run dev",
    cwd: "../..",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: false,
    env: {
      // Real Auth/Storage coverage must not silently select a manual decoded-media configuration.
      VOUCH_MEDIA_MODE: decoded ? "decoded" : "fixture",
      ...(authenticated ? {} : { VOUCH_AUTH_MODE: "fixture", NEXT_PUBLIC_AUTH_MODE: "fixture" }),
    },
    timeout: 120_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 5"] } },
  ],
});
