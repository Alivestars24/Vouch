import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CreatorFeedbackPublisher } from "@/components/campaign-workspace";
import type { CreatorFeedback, FixRequestDraft } from "@/lib/types";

const draft: FixRequestDraft = {
  id: "draft-1",
  message: "Replace the unsupported product claim.",
  createdAt: "2026-10-28T11:50:00Z",
  sent: false,
};

const published: CreatorFeedback = {
  id: "feedback-1",
  submissionId: "submission-1",
  submissionVersionId: "version-1",
  analysisId: "analysis-1",
  fixRequestDraftId: "draft-1",
  versionNo: 1,
  message: draft.message,
  startMs: 1200,
  endMs: 2400,
  invocationMode: "fixture",
  analysisStatus: "completed",
  manifestHash: "a".repeat(64),
  historical: false,
  publishedAt: "2026-10-28T12:00:00Z",
};

describe("creator feedback publication", () => {
  afterEach(cleanup);

  it("requires a prepared server draft before offering the share action", () => {
    render(<CreatorFeedbackPublisher canPublish draft={undefined} isPublishing={false} onPublish={vi.fn()} />);

    expect(screen.getByText(/prepare a revision note before sharing/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /share in creator portal/i })).not.toBeInTheDocument();
  });

  it("requires an authorized member and an explicit click to share the reviewed snapshot", async () => {
    const user = userEvent.setup();
    const onPublish = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(
      <CreatorFeedbackPublisher canPublish={false} draft={draft} invocationMode="fixture" isPublishing={false} onPublish={onPublish} />,
    );

    expect(screen.getByLabelText("Creator-visible message")).toHaveValue(draft.message);
    expect(screen.getByLabelText("Creator-visible message")).toHaveAttribute("readonly");
    expect(screen.getByText(/does not send a message or publish campaign content externally/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /share in creator portal/i })).toBeDisabled();
    expect(onPublish).not.toHaveBeenCalled();

    rerender(<CreatorFeedbackPublisher canPublish draft={draft} invocationMode="fixture" isPublishing={false} onPublish={onPublish} />);
    await user.click(screen.getByRole("button", { name: /share in creator portal/i }));
    expect(onPublish).toHaveBeenCalledOnce();
    expect(onPublish).toHaveBeenCalledWith(draft.message);
  });

  it("shows the response provenance and scoped delivery outcome", () => {
    render(
      <CreatorFeedbackPublisher canPublish draft={draft} invocationMode="fixture" isPublishing={false} onPublish={vi.fn()} published={published} />,
    );

    expect(screen.getByText("Shared to creator portal")).toBeInTheDocument();
    expect(screen.getByText(/fixture-derived/i)).toBeInTheDocument();
    expect(screen.getByText(/version 1/i)).toBeInTheDocument();
    expect(screen.getByText(/aaaaaaaaaaaa/)).toBeInTheDocument();
    expect(screen.getByText(/no external message was sent/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /share in creator portal/i })).not.toBeInTheDocument();
  });

  it("marks an earlier-version response as historical", () => {
    render(
      <CreatorFeedbackPublisher canPublish draft={draft} invocationMode="fixture" isPublishing={false} onPublish={vi.fn()} published={{ ...published, historical: true }} />,
    );

    expect(screen.getByText(/historical feedback for version 1/i)).toBeInTheDocument();
  });
});
