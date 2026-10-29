import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Session } from "@supabase/supabase-js";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/app-shell";
import { IdentityProvider } from "@/components/identity-context";
import { ApiError } from "@/lib/api";

const mocks = vi.hoisted(() => ({
  callback: undefined as ((event: string, session: unknown) => void) | undefined,
  signIn: vi.fn(), signOut: vi.fn(), workspaces: vi.fn(), google: vi.fn(), googleEnabled: false,
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/", useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api", async (original) => ({ ...await original<typeof import("@/lib/api")>(), getWorkspaces: mocks.workspaces }));
vi.mock("@/lib/supabase", () => ({
  AUTH_MODE: "supabase", SESSION_EXPIRED_EVENT: "vouch:session-expired", notifySessionExpired: vi.fn(),
  get GOOGLE_OAUTH_ENABLED() { return mocks.googleEnabled; },
  getSupabaseClient: () => ({ auth: {
    signInWithPassword: mocks.signIn, signOut: mocks.signOut, signInWithOAuth: mocks.google,
    onAuthStateChange: (callback: typeof mocks.callback) => {
      mocks.callback = callback;
      callback?.("INITIAL_SESSION", null);
      return { data: { subscription: { unsubscribe: vi.fn() } } };
    },
  } }),
}));

const session = { access_token: "test-session", user: { id: "subject-1", email: "marketer@vouch.test" } } as Session;
function renderApplication() {
  return render(<IdentityProvider><AppShell><h1>Private campaign content</h1><input aria-label="Unsubmitted caption" /></AppShell></IdentityProvider>);
}
async function signedIn() {
  await act(async () => mocks.callback?.("SIGNED_IN", session));
  await screen.findByRole("heading", { name: "Private campaign content" });
}

describe("authenticated workspace boundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.googleEnabled = false;
    mocks.signOut.mockResolvedValue({ error: null });
    mocks.workspaces.mockResolvedValue([{ id: "org-1", name: "Acme", roles: ["marketer"], membershipStatus: "active" }]);
    mocks.signIn.mockResolvedValue({ error: null });
    mocks.google.mockResolvedValue({ error: null, data: { provider: "google", url: "https://provider.example/authorize" } });
  });

  it("shows real sign-in, preserves password privacy after errors, and has no fixture selector", async () => {
    mocks.signIn.mockResolvedValue({ error: { message: "Invalid credentials" } });
    renderApplication();
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Email"), "marketer@vouch.test");
    await user.type(screen.getByLabelText("Password"), "incorrect");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sign-in failed");
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(screen.queryByLabelText("Fixture identity")).not.toBeInTheDocument();
    expect(screen.queryByText("Private campaign content")).not.toBeInTheDocument();
  });

  it("clears private content immediately on sign-out", async () => {
    renderApplication();
    await signedIn();
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in to Vouch" })).toBeInTheDocument();
    expect(screen.queryByText("Private campaign content")).not.toBeInTheDocument();
    expect(mocks.signOut).toHaveBeenCalledWith({ scope: "local" });
  });

  it("keeps an unsubmitted draft through token refresh and rejects stale-token 401 events", async () => {
    renderApplication();
    await signedIn();
    await userEvent.type(screen.getByLabelText("Unsubmitted caption"), "Keep this draft");
    await act(async () => mocks.callback?.("TOKEN_REFRESHED", { ...session, access_token: "refreshed-session" }));
    await waitFor(() => expect(mocks.workspaces).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("Unsubmitted caption")).toHaveValue("Keep this draft");
    await act(async () => window.dispatchEvent(new CustomEvent("vouch:session-expired", { detail: "test-session" })));
    expect(screen.getByText("Private campaign content")).toBeInTheDocument();
    await act(async () => window.dispatchEvent(new CustomEvent("vouch:session-expired", { detail: "refreshed-session" })));
    expect(await screen.findByRole("heading", { name: "Sign in to Vouch" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Sign in again");
  });

  it("never opens campaign content without an active membership", async () => {
    mocks.workspaces.mockResolvedValue([]);
    renderApplication();
    await act(async () => mocks.callback?.("SIGNED_IN", session));
    expect(await screen.findByRole("heading", { name: "No active workspace membership" })).toBeInTheDocument();
    expect(screen.queryByText("Private campaign content")).not.toBeInTheDocument();
  });

  it("keeps Google visible but disabled until provider setup is explicitly enabled", async () => {
    renderApplication();
    expect(await screen.findByRole("button", { name: "Continue with Google" })).toBeDisabled();
    expect(screen.getByText("Google sign-in is not configured yet. Use email and password.")).toBeInTheDocument();
    expect(mocks.google).not.toHaveBeenCalled();
  });

  it("starts the enabled Google flow without submitting password fields", async () => {
    mocks.googleEnabled = true;
    renderApplication();
    await userEvent.click(await screen.findByRole("button", { name: "Continue with Google" }));
    expect(mocks.google).toHaveBeenCalledWith({ provider: "google", options: { redirectTo: `${window.location.origin}/auth/callback` } });
    expect(screen.getByRole("button", { name: "Opening Google…" })).toBeDisabled();
    expect(mocks.signIn).not.toHaveBeenCalled();
  });

  it("offers a sanitized retry after an enabled Google start failure", async () => {
    mocks.googleEnabled = true;
    mocks.google.mockRejectedValue(new Error("raw-provider-payload"));
    renderApplication();
    await userEvent.click(await screen.findByRole("button", { name: "Continue with Google" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Google sign-in could not be started");
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeEnabled();
    expect(screen.queryByText("raw-provider-payload")).not.toBeInTheDocument();
  });

  it("keeps an unprovisioned verified account signed in without workspace access", async () => {
    mocks.workspaces.mockRejectedValue(new ApiError({ status: 403, code: "USER_NOT_PROVISIONED", message: "This account has no Vouch access." }));
    renderApplication();
    await act(async () => mocks.callback?.("SIGNED_IN", session));
    expect(await screen.findByRole("heading", { name: "No active workspace membership" })).toBeInTheDocument();
    expect(screen.getByText(/Ask your workspace administrator to grant access/)).toBeInTheDocument();
    expect(screen.queryByText("Private campaign content")).not.toBeInTheDocument();
    expect(mocks.signOut).not.toHaveBeenCalled();
  });
});
