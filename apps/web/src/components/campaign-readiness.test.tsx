import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { CampaignReadinessPanel } from "@/components/campaign-readiness";
import type { CampaignReadiness, FixtureIdentity } from "@/lib/types";

const mocks = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock("@/lib/api", () => ({
  errorMessage: (error: Error) => error.message,
  getCampaignReadiness: mocks.get,
}));

const identity: FixtureIdentity = {
  key: "member:reviewer",
  label: "Reviewer",
  hint: "",
  user: "reviewer@vouch.test",
  organizationId: "11111111-1111-4111-8111-111111111111",
  organizationLabel: "Acme",
};

const blocked: CampaignReadiness = {
  campaignId: "22222222-2222-4222-8222-222222222222",
  generationMode: "deterministic_records",
  ready: false,
  blockerCount: 1,
  actionCount: 0,
  summary: "One blocking issue remains.",
  items: [{
    id: "analysis:one:findings",
    severity: "blocker",
    category: "review",
    title: "Finding decisions still block approval",
    detail: "One finding awaits a reviewer decision.",
    actionLabel: "Review findings",
    citation: {
      sourceType: "analysis",
      sourceId: "33333333-3333-4333-8333-333333333333",
      label: "Check findings",
      href: "/campaigns/22222222-2222-4222-8222-222222222222#findings-heading",
    },
  }],
  limitations: ["This brief is derived from authorized Vouch records."],
};

beforeEach(() => {
  mocks.get.mockReset().mockResolvedValue(blocked);
});

it("shows cited blockers and refreshes the record-derived brief", async () => {
  render(
    <CampaignReadinessPanel
      campaignId={blocked.campaignId}
      identity={identity}
    />,
  );

  expect(await screen.findByText(blocked.summary)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Review findings" })).toHaveAttribute(
    "href",
    blocked.items[0].citation.href,
  );
  expect(screen.getByText("Vouch records")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Refresh brief" }));
  expect(mocks.get).toHaveBeenCalledTimes(2);
});

it("reports load failures without presenting a false ready state", async () => {
  mocks.get.mockRejectedValueOnce(new Error("Readiness service unavailable."));
  render(
    <CampaignReadinessPanel
      campaignId={blocked.campaignId}
      identity={identity}
    />,
  );

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Readiness service unavailable.",
  );
  expect(screen.queryByText("ready", { exact: false })).not.toBeInTheDocument();
});
