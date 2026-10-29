import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { WorkspaceHome } from "@/components/workspace-home";
import { getCampaigns } from "@/lib/api";
import type { Campaign } from "@/lib/types";

const { identityState } = vi.hoisted(() => ({ identityState: {
  identity: { key: "member", user: "member@vouch.test", organizationId: "organization" },
  workspace: { id: "organization", name: "Review studio", roles: ["marketer"] },
  workspaceLoading: false, workspaceError: undefined, reloadWorkspace: vi.fn(),
} }));
vi.mock("@/components/identity-context", () => ({ useIdentity: () => identityState }));
vi.mock("@/components/storage-usage", () => ({ StorageUsagePanel: () => null }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={String(href)} {...props}>{children}</a> }));
vi.mock("@/lib/api", () => ({
  getCampaigns: vi.fn(), getCapabilities: vi.fn().mockResolvedValue([]),
  getCatalog: vi.fn().mockResolvedValue({ products: [], creators: [], rulePacks: [] }),
  createCampaign: vi.fn(), errorMessage: (error: Error) => error.message,
}));

const campaigns: Campaign[] = [{
  id: "monsoon", name: "Monsoon Frames", brandName: "Frame studio", productName: "Frames",
  objective: "Review a draft", market: "IN", creatorIds: [], status: "draft", currentActions: [],
}, {
  id: "night", name: "Night Ride", brandName: "Frame studio", productName: "Frames",
  objective: "Review a revision", market: "US", creatorIds: [], status: "draft",
  currentActions: ["Review draft", "Resolve findings"],
}];

beforeEach(() => { vi.clearAllMocks(); vi.mocked(getCampaigns).mockResolvedValue(campaigns); });

it("counts actual returned actions without inventing a minimum per campaign", async () => {
  render(<WorkspaceHome />);
  const count = await screen.findByLabelText("2 campaign actions");
  expect(within(count).getByText("2")).toBeInTheDocument();
  expect(screen.getByText("2 of 2 loaded")).toBeInTheDocument();
});

it("searches loaded campaigns and offers recovery from no matches", async () => {
  render(<WorkspaceHome />);
  await screen.findByText("Night Ride", { selector: "strong" });
  const search = screen.getByRole("searchbox", { name: "Search loaded campaigns" });
  fireEvent.change(search, { target: { value: "nIgHt" } });
  expect(screen.getByText("Night Ride", { selector: "strong" })).toBeInTheDocument();
  expect(screen.queryByText("Monsoon Frames", { selector: "strong" })).not.toBeInTheDocument();
  expect(screen.getByText("1 of 2 loaded")).toBeInTheDocument();
  fireEvent.change(search, { target: { value: "unmatched" } });
  expect(screen.getByRole("heading", { name: "No matching campaigns" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
  expect(screen.getByText("Monsoon Frames", { selector: "strong" })).toBeInTheDocument();
});

it("does not announce zero work when campaign data is unavailable", async () => {
  vi.mocked(getCampaigns).mockRejectedValue(new Error("Campaign service unavailable"));
  render(<WorkspaceHome />);
  await screen.findByRole("heading", { name: "Campaign data could not be loaded" });
  await waitFor(() => expect(screen.getByLabelText("Campaign actions unavailable")).toHaveTextContent("—"));
  expect(screen.queryByLabelText("0 campaign actions")).not.toBeInTheDocument();
  expect(screen.getByText("Campaign data unavailable")).toBeInTheDocument();
  expect(screen.queryByText("0 of 0 loaded")).not.toBeInTheDocument();
});
