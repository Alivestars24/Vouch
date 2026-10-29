import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CreatorInvitation } from "@/components/creator-invitation";
import type { FixtureIdentity } from "@/lib/types";

const mocks = vi.hoisted(() => ({ create: vi.fn() }));

vi.mock("@/lib/api", async (original) => ({
  ...await original<typeof import("@/lib/api")>(),
  createGuestInvitation: mocks.create,
}));

const identity: FixtureIdentity = {
  key: "acme-marketer",
  label: "Marketer",
  hint: "",
  user: "marketer@vouch.test",
  organizationId: "11111111-1111-4111-8111-111111111111",
  organizationLabel: "Acme",
};

describe("creator invitation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.create.mockResolvedValue({
      id: "grant-1",
      campaignId: "campaign-1",
      creatorId: "creator-1",
      submissionId: "submission-1",
      allowedActions: ["read_submission", "upload_source", "submit_version"],
      expiresAt: "2026-10-28T12:00:00Z",
      invitationUrl: `http://127.0.0.1:3000/creator#invite=${"s".repeat(43)}`,
    });
  });

  it("creates one recoverable link and requires an explicit copy action", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    render(
      <CreatorInvitation
        identity={identity}
        campaignId="campaign-1"
        creatorId="creator-1"
        creatorName="Riya"
        canInvite
      />,
    );

    await user.click(screen.getByRole("button", { name: "Create private upload link" }));
    expect(mocks.create).toHaveBeenCalledOnce();
    expect(mocks.create).toHaveBeenCalledWith(identity, "campaign-1", {
      creatorId: "creator-1",
      recoveryId: expect.any(String),
    });
    expect((screen.getByDisplayValue(/\/creator#invite=/) as HTMLInputElement).readOnly).toBe(true);
    expect(writeText).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Copy link" }));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("/creator#invite="));
    expect(screen.getByRole("button", { name: "Copied" })).toBeInTheDocument();
  });

  it("does not expose invitation creation to a viewer", () => {
    render(
      <CreatorInvitation
        identity={identity}
        campaignId="campaign-1"
        creatorId="creator-1"
        creatorName="Riya"
        canInvite={false}
      />,
    );
    expect(screen.getByRole("button", { name: "Create private upload link" })).toBeDisabled();
    expect(screen.getByText(/admin or marketer/i)).toBeInTheDocument();
  });
});
