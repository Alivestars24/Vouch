import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DeletionHistory } from "@/components/deletion-history";
import type { DeletionReceipt } from "@/lib/types";

const { getHistory, retryCleanup, identity } = vi.hoisted(() => ({
  getHistory: vi.fn(),
  retryCleanup: vi.fn(),
  identity: { key: "member:org", user: "member@vouch.test", organizationId: "org" },
}));

vi.mock("@/components/identity-context", () => ({ useIdentity: () => ({ identity }) }));
vi.mock("@/lib/api", () => ({
  getDeletionRequests: getHistory,
  requestDeletion: retryCleanup,
  errorMessage: (error: Error) => error.message,
}));

const receipt: DeletionReceipt = {
  id: "receipt-1", resourceType: "media_asset", resourceId: "asset-1", status: "failed",
  notice: "Private Storage cleanup remains incomplete.", requestedByKind: "retention",
  attemptCount: 3, maxAttempts: 3, createdAt: "2026-10-22T12:00:00Z",
  lastErrorCode: "STORAGE_UNAVAILABLE",
  destinations: [{ destination: "supabase_storage", status: "retry_pending" }],
};

describe("durable deletion history", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(cleanup);

  it("recovers failed system receipts on mount and lets an authorized member retry the exact asset", async () => {
    const user = userEvent.setup();
    getHistory.mockResolvedValue([receipt]);
    const completed = { ...receipt, status: "completed", completedAt: "2026-10-22T12:01:00Z", lastErrorCode: undefined };
    retryCleanup.mockResolvedValue(completed);
    const onChange = vi.fn();
    const view = render(<DeletionHistory campaignId="campaign-1" canRetry onReceiptChange={onChange} />);
    expect(screen.getByRole("button", { name: "Loading deletion history..." })).toBeDisabled();
    await user.click(await screen.findByText(/Media Asset asset-1/));
    expect(screen.getByText(/Retention system/)).toBeVisible();
    expect(screen.getByText(/Attempts: 3. Automatic limit: 3/)).toBeVisible();
    expect(screen.getByText(/Automatic cleanup stopped/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry cleanup" }));
    await waitFor(() => expect(retryCleanup).toHaveBeenCalledWith(identity, { resourceType: "media_asset", resourceId: "asset-1" }));
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(completed));
    expect(screen.queryByRole("button", { name: "Retry cleanup" })).not.toBeInTheDocument();
    expect(getHistory).toHaveBeenCalledWith(identity, "campaign-1", expect.any(AbortSignal));
    view.unmount();
    getHistory.mockResolvedValue([completed]);
    render(<DeletionHistory campaignId="campaign-1" canRetry />);
    expect(await screen.findByText("Completed")).toBeInTheDocument();
  });

  it("shows retry timing without offering mutation to a read-only member", async () => {
    const user = userEvent.setup();
    getHistory.mockResolvedValue([{ ...receipt, status: "partial", attemptCount: 1, retryAfter: "2026-10-22T12:02:00Z" }]);
    render(<DeletionHistory campaignId="campaign-1" canRetry={false} />);
    await user.click(await screen.findByText(/Media Asset asset-1/));
    expect(screen.getByText(/Automatic retry scheduled/)).toBeVisible();
    expect(screen.getByText(/An admin or marketer can retry/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry cleanup" })).not.toBeInTheDocument();
  });

  it("handles unavailable history and an explicit refresh to an empty state", async () => {
    const user = userEvent.setup();
    getHistory.mockRejectedValueOnce(new Error("Cleanup history could not be loaded."));
    render(<DeletionHistory campaignId="campaign-1" canRetry />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cleanup history could not be loaded.");
    getHistory.mockResolvedValue([]);
    await user.click(screen.getByRole("button", { name: "Refresh deletion history" }));
    expect(await screen.findByText("No deletion requests recorded for this campaign.")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not retain campaign receipts across a scoped panel change", async () => {
    getHistory.mockResolvedValueOnce([receipt]);
    const view = render(<DeletionHistory campaignId="campaign-1" canRetry />);
    expect(await screen.findByText(/Media Asset asset-1/)).toBeInTheDocument();
    getHistory.mockImplementationOnce(() => new Promise(() => {}));
    view.rerender(<DeletionHistory campaignId="campaign-2" canRetry />);
    expect(screen.queryByText(/Media Asset asset-1/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Loading deletion history..." })).toBeDisabled();
  });

  it("distinguishes member-requested attempts beyond the automatic retry limit", async () => {
    const user = userEvent.setup();
    getHistory.mockResolvedValue([{ ...receipt, attemptCount: 4 }]);
    render(<DeletionHistory campaignId="campaign-1" canRetry />);
    await user.click(await screen.findByText(/Media Asset asset-1/));
    expect(screen.getByText(/Attempts: 4. Automatic limit: 3/)).toBeVisible();
    expect(screen.getByText(/Additional attempts were explicitly requested/)).toBeVisible();
  });
});
