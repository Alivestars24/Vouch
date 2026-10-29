import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SubmissionUploader } from "@/components/submission-uploader";
import { ApiError } from "@/lib/api";

const { upload, getNotice, identity } = vi.hoisted(() => ({ upload: vi.fn(), getNotice: vi.fn(), identity: { key: "member:org" } }));
vi.mock("@/components/identity-context", () => ({ useIdentity: () => ({ identity }) }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/api")>(),
  uploadSubmission: upload,
  getProcessingNotice: getNotice,
  createSyntheticMp4: () => new File(["fixture marker"], "synthetic.mp4", { type: "video/mp4" }),
  errorMessage: (error: Error) => error.message,
}));

const props = { campaignId: "campaign", creatorId: "creator", creatorName: "Authorized creator", canUpload: true };
const notice = { version: "notice-v1", purpose: "campaign_check", title: "Workspace processing notice", body: "Fixture processing only. Source and derivative deletion applies.",
  noticeHash: "a".repeat(64), status: "draft_local_only", publishedAt: "2026-10-23T00:00:00Z" };

describe("media-aware authorized uploader", () => {
  beforeEach(() => { vi.clearAllMocks(); getNotice.mockResolvedValue(notice); });
  afterEach(cleanup);

  it("preserves file, caption and attestation after a decode rejection, with no fixture fallback", async () => {
    const user = userEvent.setup();
    const onUploaded = vi.fn();
    upload.mockRejectedValueOnce(new Error("The media could not be decoded within supported limits."));
    render(<SubmissionUploader {...props} mediaProcessing={{ mode: "decoded" }} onUploaded={onUploaded} />);
    await waitFor(() => expect(screen.getByLabelText("MP4 or WebM video")).toBeEnabled());
    expect(screen.queryByRole("button", { name: "Use synthetic MP4" })).not.toBeInTheDocument();
    const file = new File(["corrupt media"], "draft.mp4", { type: "video/mp4" });
    await user.upload(screen.getByLabelText("MP4 or WebM video"), file);
    await user.type(screen.getByLabelText("Caption snapshot"), "Preserve my authorized caption.");
    await user.click(screen.getByRole("checkbox", { name: /authorized to upload/ }));
    await user.click(screen.getByRole("checkbox", { name: /I acknowledge the processing notice/ }));
    await user.click(screen.getByRole("button", { name: "Create submission" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be decoded");
    expect(screen.getByLabelText("Caption snapshot")).toHaveValue("Preserve my authorized caption.");
    expect(screen.getByRole("checkbox", { name: /authorized to upload/ })).toBeChecked();
    expect((screen.getByLabelText("MP4 or WebM video") as HTMLInputElement).files?.[0]).toBe(file);
    expect(screen.getByRole("button", { name: "Create submission" })).toBeEnabled();
    expect(upload).toHaveBeenCalledTimes(1);
    expect(onUploaded).not.toHaveBeenCalled();
  });

  it("enables the synthetic marker only in explicitly confirmed fixture media mode", async () => {
    const user = userEvent.setup();
    render(<SubmissionUploader {...props} mediaProcessing={{ mode: "fixture" }} onUploaded={vi.fn()} />);
    await screen.findByRole("checkbox", { name: /I acknowledge the processing notice/ });
    expect(screen.getByText("Fixture media processing")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Use synthetic MP4" }));
    expect(screen.getByText(/synthetic.mp4/)).toBeInTheDocument();
    expect(screen.getByText(/not observations of this upload/)).toBeInTheDocument();
  });

  it("does not enable upload while the configured media mode is unknown", () => {
    render(<SubmissionUploader {...props} onUploaded={vi.fn()} />);
    expect(screen.getByLabelText("MP4 or WebM video")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Create submission" })).toBeDisabled();
    expect(screen.getByText("Media processing mode unavailable")).toBeInTheDocument();
    expect(upload).not.toHaveBeenCalled();
  });

  it("rejects oversized video before creating an upload and preserves the caption", async () => {
    const user = userEvent.setup();
    render(<SubmissionUploader {...props} mediaProcessing={{ mode: "decoded" }} onUploaded={vi.fn()} />);
    await waitFor(() => expect(screen.getByLabelText("MP4 or WebM video")).toBeEnabled());
    await user.type(screen.getByLabelText("Caption snapshot"), "Keep my draft caption.");
    const file = new File([new Uint8Array(5_000_001)], "large.mp4", { type: "video/mp4" });
    await user.upload(screen.getByLabelText("MP4 or WebM video"), file);
    expect(screen.getByRole("alert")).toHaveTextContent("Export a smaller MP4 or WebM");
    expect(screen.getByLabelText("MP4 or WebM video")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("button", { name: "Create submission" })).toBeDisabled();
    expect(screen.getByLabelText("Caption snapshot")).toHaveValue("Keep my draft caption.");
    expect(upload).not.toHaveBeenCalled();
  });

  it("requires acknowledgment separately from rights and preserves the draft when a stale notice is refreshed", async () => {
    const user = userEvent.setup();
    getNotice.mockResolvedValueOnce(notice).mockResolvedValueOnce({ ...notice, version: "notice-v2", noticeHash: "b".repeat(64) });
    upload.mockRejectedValueOnce(new ApiError({ code: "NOTICE_VERSION_STALE", status: 409, message: "The processing notice changed. Review it again." }));
    render(<SubmissionUploader {...props} mediaProcessing={{ mode: "fixture" }} onUploaded={vi.fn()} />);
    await screen.findByRole("checkbox", { name: /I acknowledge the processing notice notice-v1/ });
    await user.click(screen.getByRole("button", { name: "Use synthetic MP4" }));
    await user.type(screen.getByLabelText("Caption snapshot"), "Keep this draft.");
    await user.click(screen.getByRole("checkbox", { name: /authorized to upload/ }));
    expect(screen.getByRole("button", { name: "Create submission" })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /I acknowledge the processing notice notice-v1/ }));
    await user.click(screen.getByRole("button", { name: "Create submission" }));
    const refreshed = await screen.findByRole("checkbox", { name: /I acknowledge the processing notice notice-v2/ });
    expect(refreshed).not.toBeChecked();
    expect(screen.getByLabelText("Caption snapshot")).toHaveValue("Keep this draft.");
    expect(screen.getByRole("checkbox", { name: /authorized to upload/ })).toBeChecked();
    expect(screen.getByText(/synthetic.mp4/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create submission" })).toBeDisabled();
    expect(upload).toHaveBeenCalledWith(identity, expect.objectContaining({ noticeVersion: "notice-v1", noticeAcknowledged: true, rightsAttested: true }));
    expect(getNotice).toHaveBeenCalledTimes(2);
  });

  it("blocks intake when a notice cannot load and offers an explicit retry", async () => {
    const user = userEvent.setup();
    getNotice.mockRejectedValueOnce(new Error("Notice unavailable."));
    render(<SubmissionUploader {...props} mediaProcessing={{ mode: "fixture" }} onUploaded={vi.fn()} />);
    await screen.findByText("Processing notice unavailable");
    expect(screen.getByRole("button", { name: "Use synthetic MP4" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Retry notice loading" }));
    const acknowledgment = await screen.findByRole("checkbox", { name: /I acknowledge the processing notice/ });
    expect(acknowledgment).not.toBeChecked();
    expect(upload).not.toHaveBeenCalled();
  });
});
