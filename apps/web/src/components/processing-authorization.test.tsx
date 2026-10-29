import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProcessingAuthorization } from "@/components/processing-authorization";
import type { DeletionReceipt, SubmissionVersion } from "@/lib/types";

const { withdraw, identity } = vi.hoisted(() => ({ withdraw: vi.fn(), identity: { key: "member:org" } }));
vi.mock("@/components/identity-context", () => ({ useIdentity: () => ({ identity }) }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/api")>(), withdrawProcessingAuthorization: withdraw,
}));

const version: SubmissionVersion = { id: "version", versionNo: 1, caption: "Authorized draft", superseded: false,
  authorizationStatus: "active", consentReceipt: { id: "receipt", purpose: "campaign_check", noticeVersion: "notice-v1",
    noticeHash: "a".repeat(64), acceptedAt: "2026-10-23T00:00:00Z" } };
const deletion: DeletionReceipt = { id: "deletion", resourceType: "media_asset", resourceId: "asset", status: "partial",
  notice: "Storage cleanup is pending.", requestedByKind: "member", attemptCount: 1, maxAttempts: 3,
  destinations: [{ destination: "supabase_storage", status: "retry_pending" }] };

describe("selected asset processing authorization", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(cleanup);

  it("requires deliberate confirmation and preserves a partial cleanup response after withdrawal", async () => {
    const user = userEvent.setup();
    withdraw.mockResolvedValue(deletion);
    const onWithdrawn = vi.fn();
    render(<ProcessingAuthorization version={version} canWithdraw onWithdrawn={onWithdrawn} />);
    expect(screen.getByText(/not proof of every depicted person/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /accepted notice version/ })).toHaveAttribute("href", expect.stringContaining("/notices/campaign-check/notice-v1"));
    await user.click(screen.getByRole("button", { name: "Withdraw authorization and delete" }));
    expect(screen.getByRole("button", { name: "Confirm withdrawal and delete" })).toBeDisabled();
    expect(withdraw).not.toHaveBeenCalled();
    await user.click(screen.getByRole("checkbox", { name: /withdrawal cannot reactivate/ }));
    await user.click(screen.getByRole("button", { name: "Confirm withdrawal and delete" }));
    await waitFor(() => expect(onWithdrawn).toHaveBeenCalledWith(deletion));
    expect(withdraw).toHaveBeenCalledWith(identity, "receipt");
    expect(screen.getByText("Revoked", { exact: true })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Withdraw authorization and delete" })).not.toBeInTheDocument();
    expect(screen.queryByText("Deletion complete", { exact: true })).not.toBeInTheDocument();
  });

  it("does not offer withdrawal to a viewer/reviewer without the command role", () => {
    render(<ProcessingAuthorization version={version} canWithdraw={false} onWithdrawn={vi.fn()} />);
    expect(screen.getByText(/Only an admin or marketer/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Withdraw authorization and delete" })).not.toBeInTheDocument();
  });

  it("marks legacy provenance without inventing consent or rewriting historical approvals", () => {
    render(<ProcessingAuthorization version={{ ...version, authorizationStatus: "legacy_no_notice", consentReceipt: undefined }} canWithdraw onWithdrawn={vi.fn()} />);
    expect(screen.getByText(/no recorded notice acknowledgment/)).toHaveTextContent("Historical approvals are unchanged");
    expect(screen.queryByText("Authorization active")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Withdraw authorization and delete" })).not.toBeInTheDocument();
  });
});
