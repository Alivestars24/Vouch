import { afterEach, describe, expect, it, vi } from "vitest";

import { addCreatorToCampaign, getFindCreators } from "@/lib/api";
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

describe("Find API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("normalizes returned evidence without promoting category relevance to an exact match", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ items: [{
      id: "creator-1", name: "Asha", handle: "@asha", rights_status: "authorized", evidence_timestamp: "2026-10-20T09:00:00Z",
      evidence: [{ id: "proof-1", category: "Eyewear", match_kind: "category_relevance", source_label: "Consented clip", source_uri: "fixture://proof-1", proof_kind: "video_clip", permission_status: "authorized", verification_status: "reviewed", evidence_mode: "human_curated", description: "Category proof", captured_at: "2026-10-20T09:00:00Z", start_ms: 1200, end_ms: 3200 }],
    }] }));
    vi.stubGlobal("fetch", fetcher);

    const [creator] = await getFindCreators(identity, { category: "Eyewear", matchKind: "category_relevance" });

    expect(creator).toMatchObject({ id: "creator-1", rightsStatus: "authorized", evidence: [{ matchKind: "category_relevance", sourceLabel: "Consented clip", startMs: 1200 }] });
    expect(fetcher.mock.calls[0][0]).toContain("/creators?category=Eyewear&match_kind=category_relevance");
  });

  it("adds one creator through the campaign-scoped endpoint with an idempotency key", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ id: "assignment-1", campaign_id: "campaign-1", creator_id: "creator-1", evidence_id: "proof-1", created: true }));
    vi.stubGlobal("fetch", fetcher);

    await expect(addCreatorToCampaign(identity, "campaign / one", "creator-1", "proof-1")).resolves.toEqual({ id: "assignment-1", campaignId: "campaign-1", creatorId: "creator-1", evidenceId: "proof-1", created: true });
    expect(fetcher.mock.calls[0][0]).toContain("/campaigns/campaign%20%2F%20one/creators");
    const init = fetcher.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect((init.headers as Headers).get("Idempotency-Key")).toBeTruthy();
    expect(JSON.parse(String(init.body))).toEqual({ creator_id: "creator-1", evidence_id: "proof-1" });
  });
});
