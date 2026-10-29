import { act, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OAuthCallback } from "@/components/oauth-callback";
import { GOOGLE_CALLBACK_ERROR } from "@/lib/google-oauth";
import { metadata } from "@/app/auth/callback/page";

const mocks = vi.hoisted(() => ({ router: { replace: vi.fn() }, complete: vi.fn(), signOut: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => mocks.router }));
vi.mock("@/components/identity-context", () => ({ useIdentity: () => ({ signOut: mocks.signOut }) }));
vi.mock("@/lib/google-oauth", async (original) => ({
  ...await original<typeof import("@/lib/google-oauth")>(), completeGoogleSignIn: mocks.complete,
}));

describe("public OAuth callback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.complete.mockResolvedValue(undefined);
    mocks.signOut.mockResolvedValue(undefined);
  });

  it("keeps callback data out of referrers", () => {
    expect(metadata.referrer).toBe("no-referrer");
  });

  it("returns only to the fixed workspace route after exchange", async () => {
    render(<OAuthCallback />);
    await waitFor(() => expect(mocks.router.replace).toHaveBeenCalledWith("/"));
    expect(mocks.signOut).not.toHaveBeenCalled();
  });

  it("exchanges a single-use code only once under Strict Mode", async () => {
    render(<StrictMode><OAuthCallback /></StrictMode>);
    await waitFor(() => expect(mocks.router.replace).toHaveBeenCalledWith("/"));
    expect(mocks.complete).toHaveBeenCalledOnce();
    expect(mocks.router.replace).toHaveBeenCalledOnce();
  });

  it("clears the local session on callback failure without displaying provider details", async () => {
    mocks.complete.mockRejectedValue(new Error("raw-provider-error token=synthetic"));
    render(<OAuthCallback />);
    expect(await screen.findByRole("heading", { name: "Sign-in was not completed" })).toBeInTheDocument();
    expect(screen.getByText(GOOGLE_CALLBACK_ERROR)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Return to sign in" })).toHaveAttribute("href", "/");
    expect(screen.queryByText(/raw-provider-error/)).not.toBeInTheDocument();
    expect(mocks.signOut).toHaveBeenCalledOnce();
    expect(mocks.router.replace).not.toHaveBeenCalled();
  });

  it("still shows safe recovery when remote sign-out cannot be confirmed", async () => {
    mocks.complete.mockRejectedValue(new Error("callback failed"));
    mocks.signOut.mockRejectedValue(new Error("raw-sign-out-response"));
    render(<OAuthCallback />);
    expect(await screen.findByRole("link", { name: "Return to sign in" })).toBeInTheDocument();
    expect(screen.getByText(GOOGLE_CALLBACK_ERROR)).toBeInTheDocument();
    expect(screen.queryByText(/raw-sign-out-response/)).not.toBeInTheDocument();
  });

  it("does not navigate after the callback screen is unmounted", async () => {
    let finish: () => void = () => undefined;
    mocks.complete.mockReturnValue(new Promise<void>((resolve) => { finish = resolve; }));
    const view = render(<OAuthCallback />);
    view.unmount();
    await act(async () => finish());
    expect(mocks.router.replace).not.toHaveBeenCalled();
  });
});
