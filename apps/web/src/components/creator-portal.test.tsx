import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CreatorPortal } from "@/components/creator-portal";
import { GuestPortalError } from "@/lib/guest-api";

const mocks = vi.hoisted(() => ({
  exchange: vi.fn(),
  submission: vi.fn(),
  notice: vi.fn(),
  submitDraft: vi.fn(),
  withdraw: vi.fn(),
}));

vi.mock("@/lib/guest-api", async (original) => ({
  ...await original<typeof import("@/lib/guest-api")>(),
  exchangeGuestInvitation: mocks.exchange,
  getGuestSubmission: mocks.submission,
  getGuestProcessingNotice: mocks.notice,
  submitGuestDraft: mocks.submitDraft,
  withdrawGuestSource: mocks.withdraw,
}));

const payload = {
  session_expires_at: "2026-10-25T12:30:00Z",
  campaign: { name: "Autumn frames", market: "IN", brand_name: "Acme Eyewear" },
  creator: { name: "Riya", handle: "@riya" },
  submission: {
    current_version: { id: "33333333-3333-4333-8333-333333333333", version_no: 2, caption: "A measured caption", created_at: "2026-10-25T11:00:00Z", consent_receipt_id: "44444444-4444-4444-8444-444444444444" },
    review_state: "changes_requested" as const,
    approved_version_no: null,
  },
  allowed_actions: ["read_submission"] as const,
  feedback: [{
    version_no: 2,
    message: "Please hold the product for one more beat.",
    start_ms: 1200,
    end_ms: 2600,
    invocation_mode: "fixture" as const,
    analysis_status: "completed" as const,
    manifest_hash: "b".repeat(64),
    published_at: "2026-10-25T11:30:00Z",
    historical: false,
  }],
};

describe("creator portal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/creator");
    mocks.exchange.mockResolvedValue({ status: "active", expires_at: payload.session_expires_at });
    mocks.submission.mockResolvedValue(payload);
    mocks.notice.mockResolvedValue({
      version: "guest-notice-v1",
      purpose: "campaign_check",
      title: "Creator processing notice",
      body: "Private creator processing notice.",
      notice_hash: "a".repeat(64),
      status: "draft_local_only",
      published_at: "2026-10-25T10:00:00Z",
    });
    mocks.withdraw.mockResolvedValue({ id: "55555555-5555-4555-8555-555555555555", status: "partial" });
  });

  it("scrubs the fragment before exchanging once under Strict Mode", async () => {
    window.history.replaceState({}, "", `/creator#invite=${"s".repeat(43)}`);
    const replaced = vi.spyOn(window.history, "replaceState");
    const sequence: string[] = [];
    replaced.mockImplementation((...args) => {
      sequence.push("scrub");
      return History.prototype.replaceState.apply(window.history, args);
    });
    mocks.exchange.mockImplementation(async () => { sequence.push("exchange"); });

    render(<StrictMode><CreatorPortal /></StrictMode>);

    expect(window.location.hash).toBe("");
    await screen.findByRole("heading", { name: "Autumn frames" });
    expect(sequence.slice(0, 2)).toEqual(["scrub", "exchange"]);
    expect(mocks.exchange).toHaveBeenCalledOnce();
    expect(mocks.exchange).toHaveBeenCalledWith("s".repeat(43), expect.any(AbortSignal));
    expect(mocks.submission).toHaveBeenCalledOnce();
  });

  it("resumes an existing cookie session without an invitation exchange", async () => {
    render(<CreatorPortal />);
    expect(await screen.findByRole("heading", { name: "Autumn frames" })).toBeInTheDocument();
    expect(screen.getByText("Changes requested")).toBeInTheDocument();
    expect(screen.getByText("A measured caption")).toBeInTheDocument();
    expect(screen.getByText("Please hold the product for one more beat.")).toBeInTheDocument();
    expect(screen.getByText(/Current-version feedback/)).toBeInTheDocument();
    expect(screen.getByText(/Fixture-derived Check/)).toBeInTheDocument();
    expect(mocks.exchange).not.toHaveBeenCalled();
    expect(mocks.submission).toHaveBeenCalledOnce();
  });

  it("rejects malformed fragments without sending them", async () => {
    window.history.replaceState({}, "", "/creator#invite=short&campaign=private");
    render(<CreatorPortal />);
    expect(await screen.findByRole("heading", { name: "This link has ended" })).toBeInTheDocument();
    expect(window.location.hash).toBe("");
    expect(mocks.exchange).not.toHaveBeenCalled();
    expect(mocks.submission).not.toHaveBeenCalled();
  });

  it("shows only safe recovery copy after a denied exchange", async () => {
    window.history.replaceState({}, "", `/creator#invite=${"x".repeat(43)}`);
    mocks.exchange.mockRejectedValue(new GuestPortalError("ended"));
    render(<CreatorPortal />);
    expect(await screen.findByRole("heading", { name: "This link has ended" })).toBeInTheDocument();
    expect(screen.queryByText(/grant|revoked|expired token/i)).not.toBeInTheDocument();
    await waitFor(() => expect(mocks.submission).not.toHaveBeenCalled());
  });

  it("shows first-draft intake only with both mutation actions and no current version", async () => {
    mocks.submission.mockResolvedValueOnce({
      ...payload,
      submission: {
        current_version: null,
        review_state: "awaiting_brand_review",
        approved_version_no: null,
      },
      allowed_actions: ["read_submission", "upload_source", "submit_version"],
      feedback: [],
    });

    render(<CreatorPortal />);
    expect(await screen.findByRole("heading", { name: "Submit your first draft" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit draft" })).toBeDisabled();
  });

  it("does not expose mutation UI without the complete action pair", async () => {
    mocks.submission.mockResolvedValueOnce({
      ...payload,
      submission: {
        current_version: null,
        review_state: "awaiting_brand_review",
        approved_version_no: null,
      },
      allowed_actions: ["read_submission", "upload_source"],
      feedback: [],
    });

    render(<CreatorPortal />);
    await screen.findByRole("heading", { name: "Autumn frames" });
    expect(screen.queryByRole("heading", { name: "Submit your first draft" })).not.toBeInTheDocument();
    expect(screen.getByText(/does not currently allow an upload/i)).toBeInTheDocument();
    expect(mocks.notice).not.toHaveBeenCalled();
  });

  it("offers the exact next revision when the mutation scope remains active", async () => {
    mocks.submission.mockResolvedValueOnce({
      ...payload,
      allowed_actions: ["read_submission", "upload_source", "submit_version"],
    });

    render(<CreatorPortal />);
    await screen.findByRole("heading", { name: "Autumn frames" });
    expect(screen.getByRole("heading", { name: "Submit a revision" })).toBeInTheDocument();
    expect(screen.getByText("Version 3")).toBeInTheDocument();
    expect(mocks.notice).toHaveBeenCalledOnce();
  });

  it("requires explicit confirmation before withdrawing the exact source", async () => {
    const user = userEvent.setup();
    render(<CreatorPortal />);
    await screen.findByRole("heading", { name: "Autumn frames" });

    await user.click(screen.getByRole("button", { name: "Withdraw authorization and delete" }));
    expect(mocks.withdraw).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirm withdrawal" }));

    await waitFor(() => expect(mocks.withdraw).toHaveBeenCalledWith("44444444-4444-4444-8444-444444444444"));
    expect(screen.getByRole("heading", { name: "Processing authorization withdrawn" })).toBeInTheDocument();
    expect(screen.getByText(/cleanup is still being confirmed/i)).toBeInTheDocument();
  });
});
