import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CreatorSubmissionForm } from "@/components/creator-submission-form";
import { GuestActionError, GuestPortalError, type GuestProcessingNotice, type GuestSubmission } from "@/lib/guest-api";

const mocks = vi.hoisted(() => ({
  getNotice: vi.fn(),
  submitDraft: vi.fn(),
}));

vi.mock("@/lib/guest-api", async (original) => ({
  ...await original<typeof import("@/lib/guest-api")>(),
  getGuestProcessingNotice: mocks.getNotice,
  submitGuestDraft: mocks.submitDraft,
}));

const notice: GuestProcessingNotice = {
  version: "guest-notice-v1",
  purpose: "campaign_check",
  title: "Creator processing notice",
  body: "Vouch will keep this source and declared derivatives for the stated review period.",
  notice_hash: "a".repeat(64),
  status: "draft_local_only",
  published_at: "2026-10-26T09:00:00Z",
};

const submitted: GuestSubmission = {
  session_expires_at: "2026-10-26T10:00:00Z",
  campaign: { name: "Autumn frames", market: "IN", brand_name: "Acme Eyewear" },
  creator: { name: "Riya", handle: "@riya" },
  submission: {
    current_version: {
      id: "33333333-3333-4333-8333-333333333333",
      version_no: 1,
      caption: "My first draft",
      created_at: "2026-10-26T09:10:00Z",
      consent_receipt_id: "44444444-4444-4444-8444-444444444444",
    },
    review_state: "awaiting_brand_review",
    approved_version_no: null,
  },
  allowed_actions: ["read_submission"],
  feedback: [],
};

function video(contents = "video"): File {
  return new File([contents], "creator-draft.mp4", { type: "video/mp4" });
}

async function completeForm(user: ReturnType<typeof userEvent.setup>, file = video()) {
  await user.upload(await screen.findByLabelText("MP4 or WebM video"), file);
  await user.type(screen.getByLabelText("Caption snapshot"), "My first draft");
  await user.click(screen.getByRole("checkbox", { name: /I have the rights/i }));
  await user.click(screen.getByRole("checkbox", { name: /I acknowledge creator processing notice guest-notice-v1/i }));
}

describe("creator submission form", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getNotice.mockResolvedValue(notice);
  });

  afterEach(cleanup);

  it("keeps retry keys stable and clears the draft only after authoritative success", async () => {
    const user = userEvent.setup();
    const onSubmitted = vi.fn();
    mocks.submitDraft
      .mockRejectedValueOnce(new GuestActionError({
        status: 409,
        code: "GUEST_UPLOAD_QUOTA_EXCEEDED",
        message: "This link has reached its upload allowance.",
      }))
      .mockResolvedValueOnce(submitted);

    render(<CreatorSubmissionForm currentVersion={null} onSubmitted={onSubmitted} onEnded={vi.fn()} />);
    await completeForm(user);

    await user.click(screen.getByRole("button", { name: "Submit draft" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("upload allowance");
    expect(screen.getByLabelText("Caption snapshot")).toHaveValue("My first draft");
    expect((screen.getByLabelText("MP4 or WebM video") as HTMLInputElement).files?.[0]?.name)
      .toBe("creator-draft.mp4");

    await user.click(screen.getByRole("button", { name: "Submit draft" }));
    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith(submitted));

    const first = mocks.submitDraft.mock.calls[0][0];
    const second = mocks.submitDraft.mock.calls[1][0];
    expect(second.intentIdempotencyKey).toBe(first.intentIdempotencyKey);
    expect(second.versionIdempotencyKey).toBe(first.versionIdempotencyKey);
    expect(first).toMatchObject({
      caption: "My first draft",
      rightsAttested: true,
      noticeVersion: "guest-notice-v1",
      noticeAcknowledged: true,
      expectedCurrentVersionId: null,
      expectedVersionNo: 1,
    });
    expect(screen.getByLabelText("Caption snapshot")).toHaveValue("");
    expect((screen.getByLabelText("MP4 or WebM video") as HTMLInputElement).files).toHaveLength(0);
    expect(screen.getByRole("checkbox", { name: /I have the rights/i })).not.toBeChecked();
  });

  it("reloads a stale notice, clearing only its acknowledgment", async () => {
    const user = userEvent.setup();
    const nextNotice = {
      ...notice,
      version: "guest-notice-v2",
      notice_hash: "b".repeat(64),
    } satisfies GuestProcessingNotice;
    mocks.getNotice.mockResolvedValueOnce(notice).mockResolvedValueOnce(nextNotice);
    mocks.submitDraft.mockRejectedValueOnce(new GuestActionError({
      status: 409,
      code: "NOTICE_VERSION_STALE",
      message: "The processing notice changed. Review it again.",
    }));

    render(<CreatorSubmissionForm currentVersion={null} onSubmitted={vi.fn()} onEnded={vi.fn()} />);
    await completeForm(user);
    await user.click(screen.getByRole("button", { name: "Submit draft" }));

    const acknowledgment = await screen.findByRole("checkbox", {
      name: /I acknowledge creator processing notice guest-notice-v2/i,
    });
    expect(acknowledgment).not.toBeChecked();
    expect(screen.getByLabelText("Caption snapshot")).toHaveValue("My first draft");
    expect(screen.getByRole("checkbox", { name: /I have the rights/i })).toBeChecked();
    expect((screen.getByLabelText("MP4 or WebM video") as HTMLInputElement).files?.[0]?.name)
      .toBe("creator-draft.mp4");
  });

  it("rejects unsupported and oversized media before making a mutation request", async () => {
    const user = userEvent.setup({ applyAccept: false });
    render(<CreatorSubmissionForm currentVersion={null} onSubmitted={vi.fn()} onEnded={vi.fn()} />);
    const input = await screen.findByLabelText("MP4 or WebM video");

    await user.upload(input, new File(["svg"], "unsafe.svg", { type: "image/svg+xml" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Select an MP4 or WebM video");
    expect(screen.getByRole("button", { name: "Submit draft" })).toBeDisabled();

    await user.upload(input, new File([new Uint8Array(5_000_001)], "large.mp4", { type: "video/mp4" }));
    expect(screen.getByRole("alert")).toHaveTextContent("up to 5 MB");
    expect(mocks.submitDraft).not.toHaveBeenCalled();
  });

  it("turns an ended guest session into the portal ended state", async () => {
    const user = userEvent.setup();
    const onEnded = vi.fn();
    mocks.submitDraft.mockRejectedValueOnce(new GuestPortalError("ended"));

    render(<CreatorSubmissionForm currentVersion={null} onSubmitted={vi.fn()} onEnded={onEnded} />);
    await completeForm(user);
    await user.click(screen.getByRole("button", { name: "Submit draft" }));
    await waitFor(() => expect(onEnded).toHaveBeenCalledOnce());
    expect(screen.queryByText(/GUEST_ACCESS_ENDED/)).not.toBeInTheDocument();
  });
});
