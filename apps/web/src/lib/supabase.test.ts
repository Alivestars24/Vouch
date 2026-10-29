import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ createClient: vi.fn() }));
vi.mock("@supabase/supabase-js", () => ({ createClient: mocks.createClient }));

describe("Supabase browser authentication configuration", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    vi.stubEnv("NEXT_PUBLIC_AUTH_MODE", "supabase");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://127.0.0.1:54321");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "synthetic-publishable");
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_OAUTH_ENABLED", undefined);
    mocks.createClient.mockReturnValue({ auth: {} });
  });
  afterEach(() => vi.unstubAllEnvs());

  it("uses PKCE with manual URL exchange while retaining normal persisted/refreshing sessions", async () => {
    const { getSupabaseClient, GOOGLE_OAUTH_ENABLED } = await import("@/lib/supabase");
    const client = getSupabaseClient();
    expect(getSupabaseClient()).toBe(client);
    expect(mocks.createClient).toHaveBeenCalledOnce();
    expect(mocks.createClient).toHaveBeenCalledWith("http://127.0.0.1:54321", "synthetic-publishable", {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false, flowType: "pkce" },
    });
    expect(GOOGLE_OAUTH_ENABLED).toBe(false);
  });

  it("requires explicit true activation in Supabase mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_OAUTH_ENABLED", "true");
    expect((await import("@/lib/supabase")).GOOGLE_OAUTH_ENABLED).toBe(true);
  });

  it("cannot activate Google in fixture mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_OAUTH_ENABLED", "true");
    vi.stubEnv("NEXT_PUBLIC_AUTH_MODE", "fixture");
    const config = await import("@/lib/supabase");
    expect(config.GOOGLE_OAUTH_ENABLED).toBe(false);
    expect(() => config.getSupabaseClient()).toThrow("not enabled");
    expect(mocks.createClient).not.toHaveBeenCalled();
  });
});
