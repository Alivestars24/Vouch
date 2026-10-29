import { afterEach, expect, it, vi } from "vitest";
import { FIXTURE_IDENTITIES, getStorageUsage, uploadSubmission } from "@/lib/api";

vi.mock("@/lib/supabase", () => ({ AUTH_MODE: "fixture", notifySessionExpired: vi.fn() }));

const usage = { limit_bytes: 500_000_000, used_bytes: 10, reserved_bytes: 5_000_000,
  pending_cleanup_bytes: 2, available_bytes: 494_999_988, max_upload_bytes: 5_000_000, storage_backend: "supabase" };
const json = (body: unknown) => new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

it("sends current workspace scope and preserves the typed accounting categories", async () => {
  const fetch = vi.fn().mockResolvedValue(json(usage));
  vi.stubGlobal("fetch", fetch);
  expect(await getStorageUsage(FIXTURE_IDENTITIES[0])).toEqual(usage);
  expect(fetch.mock.calls[0][0]).toContain("/storage/usage");
  expect(fetch.mock.calls[0][1].headers.get("X-Organization-Id")).toBe(FIXTURE_IDENTITIES[0].organizationId);
});

it.each([
  {}, { ...usage, used_bytes: -1 }, { ...usage, reserved_bytes: "5000000" },
  { ...usage, pending_cleanup_bytes: 1.5 }, { ...usage, available_bytes: usage.limit_bytes },
  { ...usage, storage_backend: "public" }, { ...usage, max_upload_bytes: 0 },
])("rejects malformed or contradictory usage instead of showing free space: %j", async (body) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(body)));
  await expect(getStorageUsage(FIXTURE_IDENTITIES[0])).rejects.toMatchObject({ code: "STORAGE_USAGE_UNAVAILABLE" });
});

it.each([0, 5_000_001])("rejects an invalid %s byte upload before any network request", async (size) => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const file = new File([new Uint8Array(size)], "draft.mp4", { type: "video/mp4" });
  await expect(uploadSubmission(FIXTURE_IDENTITIES[0], { campaignId: "campaign", creatorId: "creator", file,
    caption: "Draft", rightsAttested: true, noticeVersion: "notice", noticeAcknowledged: true }))
    .rejects.toMatchObject({ code: "UPLOAD_SIZE_INVALID" });
  expect(fetch).not.toHaveBeenCalled();
});
