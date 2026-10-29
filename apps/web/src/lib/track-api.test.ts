import { afterEach, describe, expect, it, vi } from "vitest";

import { getCampaignTrack, recordTestOutcomeEvent } from "@/lib/api";
import type { FixtureIdentity } from "@/lib/types";

vi.mock("@/lib/supabase", () => ({ AUTH_MODE: "fixture", notifySessionExpired: vi.fn() }));

const identity: FixtureIdentity = {
  key: "member", label: "Member", hint: "", user: "member@vouch.test",
  organizationId: "11111111-1111-4111-8111-111111111111", organizationLabel: "Acme",
};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});

describe("Track API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps test and live summaries separate while normalizing currency totals", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({
      campaign_id: "campaign-1",
      freshness_at: "2026-10-29T09:00:00Z",
      test: { clicks: 2, orders: 1, refunds: 1, conversion_rate: 0.5, totals_by_currency: { INR: { gross_minor: 12500, refunded_minor: 2500, net_minor: 10000 } } },
      live: { clicks: 0, orders: 0, refunds: 0, conversion_rate: null, totals_by_currency: {} },
      events: [],
    })));

    await expect(getCampaignTrack(identity, "campaign-1")).resolves.toMatchObject({
      campaignId: "campaign-1",
      test: { conversionRate: 0.5, totalsByCurrency: { INR: { netMinor: 10000 } } },
      live: { conversionRate: undefined, totalsByCurrency: {} },
    });
  });

  it("posts only explicitly labeled test-event input", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({
      id: "event-1", creator_id: "creator-1", event_kind: "order", environment: "test",
      external_event_id: "stable-1", order_external_id: "order-1", amount_minor: 12500,
      currency: "INR", attribution_status: "attributed", attribution_method: "test_roster",
      occurred_at: "2026-10-29T09:00:00Z", received_at: "2026-10-29T09:00:01Z",
    }, 201));
    vi.stubGlobal("fetch", fetcher);

    await recordTestOutcomeEvent(identity, "campaign / one", {
      creatorId: "creator-1", eventKind: "order", externalEventId: "stable-1",
      orderExternalId: "order-1", amountMinor: 12500, currency: "INR",
      occurredAt: "2026-10-29T09:00:00Z",
    });

    expect(fetcher.mock.calls[0][0]).toContain("/campaigns/campaign%20%2F%20one/track/test-events");
    expect(JSON.parse(String((fetcher.mock.calls[0][1] as RequestInit).body))).toEqual({
      creator_id: "creator-1", event_kind: "order", external_event_id: "stable-1",
      order_external_id: "order-1", amount_minor: 12500, currency: "INR",
      occurred_at: "2026-10-29T09:00:00Z",
    });
  });
});
