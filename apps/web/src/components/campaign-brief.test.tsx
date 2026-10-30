import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { CampaignBriefPanel } from "@/components/campaign-brief";
import type { CampaignBrief, FixtureIdentity } from "@/lib/types";

const mocks = vi.hoisted(() => ({
  createClaim: vi.fn(),
  createRequirement: vi.fn(),
  get: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  createCampaignRequirement: mocks.createRequirement,
  createProductClaim: mocks.createClaim,
  errorMessage: (error: Error) => error.message,
  getCampaignBrief: mocks.get,
}));

const identity: FixtureIdentity = {
  key: "acme-marketer",
  label: "Marketer",
  hint: "",
  user: "marketer@vouch.test",
  organizationId: "11111111-1111-4111-8111-111111111111",
  organizationLabel: "Acme",
};

const brief: CampaignBrief = {
  campaignId: "22222222-2222-4222-8222-222222222222",
  claims: [],
  requirements: [{
    id: "33333333-3333-4333-8333-333333333333",
    campaignId: "22222222-2222-4222-8222-222222222222",
    kind: "product_visibility",
    label: "Show the correct product",
    required: true,
    createdAt: "2026-10-30T00:00:00Z",
  }],
  assessments: [{
    requirementId: "33333333-3333-4333-8333-333333333333",
    submissionId: "44444444-4444-4444-8444-444444444444",
    submissionVersionId: "55555555-5555-4555-8555-555555555555",
    analysisId: "66666666-6666-4666-8666-666666666666",
    status: "unknown",
    detail: "Visual evidence is incomplete, so the result is unknown.",
    evidenceIds: [],
  }],
  limitations: ["Missing evidence is unknown, never a pass."],
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.get.mockResolvedValue(brief);
  mocks.createRequirement.mockResolvedValue({});
  mocks.createClaim.mockResolvedValue({});
});

it("shows requirement status without converting incomplete evidence into a pass", async () => {
  render(
    <CampaignBriefPanel
      campaignId={brief.campaignId}
      productId="77777777-7777-4777-8777-777777777777"
      identity={identity}
      canManage={false}
    />,
  );

  expect(await screen.findByText("Show the correct product")).toBeInTheDocument();
  expect(screen.getByText("Visual evidence is incomplete, so the result is unknown.")).toBeInTheDocument();
  expect(screen.getByText("Missing evidence is unknown, never a pass.")).toBeInTheDocument();
  expect(screen.queryByText("Add brief requirement")).not.toBeInTheDocument();
});

it("lets a marketer add a concrete caption requirement", async () => {
  const user = userEvent.setup();
  render(
    <CampaignBriefPanel
      campaignId={brief.campaignId}
      productId="77777777-7777-4777-8777-777777777777"
      identity={identity}
      canManage
    />,
  );
  await screen.findByText("Show the correct product");
  fireEvent.click(screen.getByText("Add brief requirement"));
  await user.selectOptions(screen.getByLabelText("Requirement type"), "cta");
  await user.type(screen.getByLabelText("Reviewer-facing requirement"), "Use the campaign CTA");
  await user.type(screen.getByLabelText("Expected wording"), "Shop now");
  await user.click(screen.getByRole("button", { name: "Add requirement" }));

  expect(mocks.createRequirement).toHaveBeenCalledWith(
    identity,
    brief.campaignId,
    {
      kind: "cta",
      label: "Use the campaign CTA",
      expectedText: "Shop now",
      claimId: undefined,
    },
  );
});
