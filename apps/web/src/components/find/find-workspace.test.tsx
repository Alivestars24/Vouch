import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FindWorkspace } from "@/components/find/find-workspace";

const mocks = vi.hoisted(() => ({
  getFindCreators: vi.fn(),
  getCampaigns: vi.fn(),
  addCreatorToCampaign: vi.fn(),
}));

vi.mock("@/components/identity-context", () => ({
  useIdentity: () => ({
    identity: { key: "member", label: "Member", hint: "", user: "member@vouch.test", organizationId: "org-1", organizationLabel: "Acme" },
    workspace: { id: "org-1", name: "Acme Eyewear", roles: ["marketer"], membershipStatus: "active" },
    workspaceLoading: false,
    reloadWorkspace: vi.fn(),
  }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, ...mocks };
});

const creators = [
  {
    id: "creator-1", name: "Asha Rao", handle: "@asha", rightsStatus: "authorized", evidenceTimestamp: "2026-10-20T09:00:00Z",
    evidence: [{ id: "proof-1", productId: "product-1", category: "Eyewear", matchKind: "exact_product", sourceLabel: "Authorized launch clip", sourceUri: "https://example.test/proof", proofKind: "video_clip", permissionStatus: "authorized", verificationStatus: "verified", evidenceMode: "human_curated", description: "Shows the campaign frame in an authorized launch clip.", capturedAt: "2026-10-20T09:00:00Z", startMs: 1000, endMs: 4200 }],
  },
  {
    id: "creator-2", name: "Neel Shah", handle: "@neel", rightsStatus: "reviewed", evidenceTimestamp: "2026-10-19T08:00:00Z",
    evidence: [{ id: "proof-2", category: "Skincare", matchKind: "category_relevance", sourceLabel: "Consented portfolio", proofKind: "portfolio_entry", permissionStatus: "authorized", verificationStatus: "reviewed", evidenceMode: "human_curated", description: "Category-level skincare example; not an exact brand match.", capturedAt: "2026-10-19T08:00:00Z" }],
  },
];

const campaign = {
  id: "campaign-1", name: "Monsoon Frames", objective: "Review launch", market: "IN", brandName: "Acme Eyewear", productName: "Monsoon Frame", productId: "product-1", creatorIds: [], status: "draft", currentActions: [],
};

describe("FindWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getFindCreators.mockResolvedValue(creators);
    mocks.getCampaigns.mockResolvedValue([campaign]);
    mocks.addCreatorToCampaign.mockResolvedValue({ id: "assignment-1", campaignId: "campaign-1", creatorId: "creator-1", evidenceId: "proof-1", created: true });
  });

  it("distinguishes exact-product proof from category relevance and exposes provenance", async () => {
    render(<FindWorkspace />);

    expect(await screen.findByRole("heading", { name: "Creator collection" })).toBeInTheDocument();
    expect(screen.getByText("Exact product evidence", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("Category relevance", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Authorized launch clip" })).toHaveAttribute("href", "https://example.test/proof");
    expect(screen.getByText("Authorized", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getAllByText(/20 Oct 2026/).length).toBeGreaterThan(0);
  });

  it("filters the local collection and uses the bounded empty-state language", async () => {
    const user = userEvent.setup();
    render(<FindWorkspace />);
    await screen.findByRole("heading", { name: "Asha Rao" });

    await user.type(screen.getByRole("searchbox", { name: "Search evidence" }), "no-such-candidate");

    expect(screen.getByRole("heading", { name: "No candidates in this collection match your filters" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByText("Neel Shah")).toBeInTheDocument();
  });

  it("adds a creator to the selected roster and keeps outreach draft-only", async () => {
    const user = userEvent.setup();
    render(<FindWorkspace />);
    await screen.findByRole("heading", { name: "Asha Rao" });

    await user.click(screen.getByRole("button", { name: "Add to campaign" }));
    await waitFor(() => expect(mocks.addCreatorToCampaign).toHaveBeenCalledWith(expect.any(Object), "campaign-1", "creator-1", "proof-1"));
    expect(screen.getByText("Asha Rao was added to the selected campaign roster.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Draft outreach" }));
    expect(screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Editable message draft" }).value).toContain("Monsoon Frames");
    expect(screen.getByText("Draft prepared locally. No message was sent.")).toBeInTheDocument();
    expect(mocks.addCreatorToCampaign).toHaveBeenCalledTimes(1);
  });
});
