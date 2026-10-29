import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { completeGoogleSignIn, GOOGLE_CALLBACK_ERROR, GOOGLE_SIGN_IN_ERROR, startGoogleSignIn } from "@/lib/google-oauth";

const mocks = vi.hoisted(() => ({ enabled: true, mode: "supabase", oauth: vi.fn(), exchange: vi.fn() }));
vi.mock("@/lib/supabase", () => ({
  get AUTH_MODE() { return mocks.mode; },
  get GOOGLE_OAUTH_ENABLED() { return mocks.enabled; },
  getSupabaseClient: () => ({ auth: { signInWithOAuth: mocks.oauth, exchangeCodeForSession: mocks.exchange } }),
}));

describe("Google PKCE browser transport", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.enabled = true;
    mocks.mode = "supabase";
    mocks.oauth.mockResolvedValue({ error: null, data: { provider: "google", url: "https://provider.example/authorize" } });
    mocks.exchange.mockResolvedValue({ error: null, data: { session: { access_token: "synthetic-session" } } });
  });
  afterEach(() => window.history.replaceState({}, "", "/"));

  it("always starts Google with the fixed same-origin callback, never a caller redirect", async () => {
    window.history.replaceState({}, "", "/?next=https://untrusted.invalid");
    await startGoogleSignIn();
    expect(mocks.oauth).toHaveBeenCalledWith({ provider: "google", options: { redirectTo: `${window.location.origin}/auth/callback` } });
  });

  it("does not call the SDK while Google is disabled", async () => {
    mocks.enabled = false;
    await expect(startGoogleSignIn()).rejects.toThrow("not enabled yet");
    expect(mocks.oauth).not.toHaveBeenCalled();
  });

  it("does not start OAuth in fixture mode", async () => {
    mocks.mode = "fixture";
    await expect(startGoogleSignIn()).rejects.toThrow("not enabled yet");
    expect(mocks.oauth).not.toHaveBeenCalled();
  });

  it("sanitizes a provider start failure", async () => {
    mocks.oauth.mockResolvedValue({ error: { message: "raw-provider-error secret=synthetic" } });
    await expect(startGoogleSignIn()).rejects.toThrow(GOOGLE_SIGN_IN_ERROR);
  });

  it("sanitizes a thrown transport failure", async () => {
    mocks.oauth.mockRejectedValue(new Error("raw response payload"));
    await expect(startGoogleSignIn()).rejects.toThrow(GOOGLE_SIGN_IN_ERROR);
  });

  it("scrubs callback data before exchange and preserves the SDK PKCE flow id", async () => {
    window.history.replaceState({}, "", "/auth/callback?code=synthetic-code&sb_flow_id=synthetic-flow&next=https://untrusted.invalid");
    mocks.exchange.mockImplementation(async () => {
      expect(window.location.search).toBe("");
      expect(window.location.hash).toBe("");
      return { error: null, data: { session: { access_token: "synthetic-session" } } };
    });
    await completeGoogleSignIn();
    expect(mocks.exchange).toHaveBeenCalledWith("synthetic-code", { flowId: "synthetic-flow" });
    expect(window.location.pathname).toBe("/auth/callback");
  });

  it("supports a single PKCE exchange without an explicit flow id", async () => {
    window.history.replaceState({}, "", "/auth/callback?code=synthetic-code");
    await completeGoogleSignIn();
    expect(mocks.exchange).toHaveBeenCalledWith("synthetic-code", undefined);
  });

  it.each([
    "/auth/callback", "/auth/callback?code=one&code=two", "/auth/callback?code=one#error=implicit",
    "/auth/callback?error=access_denied&error_description=raw-provider-payload",
    "/auth/callback?code=one&error_code=denied", "/auth/callback?code=one&sb_flow_id=a&sb_flow_id=b",
    "/?code=unexpected-route",
  ])("rejects and scrubs malformed or failed callback %s", async (path) => {
    window.history.replaceState({}, "", path);
    await expect(completeGoogleSignIn()).rejects.toThrow(GOOGLE_CALLBACK_ERROR);
    expect(mocks.exchange).not.toHaveBeenCalled();
    expect(window.location.search).toBe("");
    expect(window.location.hash).toBe("");
  });

  it("does not exchange a callback when activation is disabled", async () => {
    mocks.enabled = false;
    window.history.replaceState({}, "", "/auth/callback?code=synthetic-code");
    await expect(completeGoogleSignIn()).rejects.toThrow(GOOGLE_CALLBACK_ERROR);
    expect(mocks.exchange).not.toHaveBeenCalled();
  });

  it("treats a missing/expired verifier or failed exchange as a generic failure", async () => {
    mocks.exchange.mockResolvedValue({ error: { message: "raw-provider-verifier-error" }, data: { session: null } });
    window.history.replaceState({}, "", "/auth/callback?code=synthetic-code");
    await expect(completeGoogleSignIn()).rejects.toThrow(GOOGLE_CALLBACK_ERROR);
  });

  it("never accepts a successful response without a session", async () => {
    mocks.exchange.mockResolvedValue({ error: null, data: { session: null } });
    window.history.replaceState({}, "", "/auth/callback?code=synthetic-code");
    await expect(completeGoogleSignIn()).rejects.toThrow(GOOGLE_CALLBACK_ERROR);
  });
});
