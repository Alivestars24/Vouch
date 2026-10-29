import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CampaignTable } from "@/components/workspace-home";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={String(href)} {...props}>{children}</a>
  ),
}));

describe("CampaignTable", () => {
  it("shows the pinned rule pack and next review action", () => {
    render(
      <CampaignTable campaigns={[{
        id: "campaign-1",
        name: "Monsoon Frames",
        objective: "Review launch draft",
        market: "IN",
        brandName: "Acme Eyewear",
        productName: "Monsoon Frame",
        creatorIds: ["creator-1"],
        status: "draft",
        currentActions: ["Upload an authorized draft"],
        pinnedRulePack: {
          id: "pack-1",
          name: "India launch review",
          version: "1.0",
          reviewStatus: "draft",
        },
      }]} />,
    );

    expect(screen.getByText("Monsoon Frames", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("Upload an authorized draft")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open.*Monsoon Frames/ })).toHaveAttribute(
      "href",
      "/campaigns/campaign-1",
    );
  });
});
