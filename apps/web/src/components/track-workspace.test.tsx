import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TrackWorkspace } from "@/components/track-workspace";

const identity = { key: "member", label: "Member", hint: "", user: "member@vouch.test", organizationId: "org-1", organizationLabel: "Acme" };
const workspace = { id: "org-1", name: "Acme", roles: ["marketer"], membershipStatus: "active" };
const mocks = vi.hoisted(() => ({ getCampaigns: vi.fn(), getCatalog: vi.fn(), getCampaignTrack: vi.fn(), recordTestOutcomeEvent: vi.fn() }));

vi.mock("@/components/identity-context", () => ({ useIdentity: () => ({ identity, workspace, workspaceLoading: false, reloadWorkspace: vi.fn() }) }));
vi.mock("@/lib/api", async (importOriginal) => ({ ...await importOriginal<typeof import("@/lib/api")>(), ...mocks }));

describe("TrackWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getCampaigns.mockResolvedValue([{ id: "campaign-1", name: "Monsoon", objective: "Demo", market: "IN", brandName: "Acme", creatorIds: ["creator-1"], status: "active", currentActions: [] }]);
    mocks.getCatalog.mockResolvedValue({ products: [], rulePacks: [], creators: [{ id: "creator-1", name: "Asha", handle: "@asha", rightsStatus: "authorized" }] });
    mocks.getCampaignTrack.mockResolvedValue({
      campaignId: "campaign-1", freshnessAt: "2026-10-29T09:00:00Z",
      test: { clicks: 2, orders: 1, refunds: 0, conversionRate: 0.5, totalsByCurrency: { INR: { grossMinor: 12500, refundedMinor: 0, netMinor: 12500 } } },
      live: { clicks: 0, orders: 0, refunds: 0, totalsByCurrency: {} }, events: [],
    });
  });

  it("shows test outcomes without presenting them as live revenue", async () => {
    render(<TrackWorkspace />);

    expect(await screen.findByRole("heading", { name: "Test outcomes" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Live outcomes" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /^Test attribution funnel/ })).toBeInTheDocument();
    expect(screen.getByText("50.0% of attributed clicks became orders")).toBeInTheDocument();
    expect(screen.getByText("Live ingestion is not configured. Test events never appear in this panel or in real outcome metrics.")).toBeInTheDocument();
    expect(screen.getAllByText("₹125.00")).toHaveLength(2);
    await waitFor(() => expect(screen.getByRole("button", { name: "Record test click" })).toBeEnabled());
  });
});
