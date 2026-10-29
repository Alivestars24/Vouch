import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildIdentityHeaders, createGuestInvitation, getCampaigns, getDeletionRequests, getJob, getMediaProcessing, getProcessingNotice, getSubmissions, getWorkspaces, publishCreatorFeedback, requestDeletion, startCheck, uploadSubmission, withdrawProcessingAuthorization } from "@/lib/api";
import type { FixtureIdentity } from "@/lib/types";

const { expired } = vi.hoisted(() => ({ expired: vi.fn() }));
vi.mock("@/lib/supabase", () => ({ AUTH_MODE: "supabase", notifySessionExpired: expired }));

const identity: FixtureIdentity = {
  key: "subject:organization", label: "Member", hint: "", user: "member@vouch.test",
  organizationId: "11111111-1111-4111-8111-111111111111", organizationLabel: "Acme", accessToken: "test-bearer",
};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

describe("authenticated API transport", () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => vi.unstubAllGlobals());

  it("discovers memberships with bearer only, then scopes member requests", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ items: [] }));
    vi.stubGlobal("fetch", fetcher);
    await getWorkspaces({ ...identity, organizationId: "" });
    const discovery = fetcher.mock.calls[0][1].headers as Headers;
    expect(discovery.get("Authorization")).toBe("Bearer test-bearer");
    expect(discovery.has("X-Organization-Id")).toBe(false);
    expect(discovery.has("X-Fixture-User")).toBe(false);
    await getCampaigns(identity);
    const scoped = fetcher.mock.calls[1][1].headers as Headers;
    expect(scoped.get("X-Organization-Id")).toBe(identity.organizationId);
    expect(scoped.has("X-Fixture-Roles")).toBe(false);
  });

  it("never falls back to fixture identity when a session is absent", () => {
    expect(() => buildIdentityHeaders({ ...identity, accessToken: undefined })).toThrow("Sign in");
    expect(() => buildIdentityHeaders({ ...identity, organizationId: "" })).toThrow("Select an active workspace");
  });

  it("notifies session recovery after an API 401", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ error: { message: "Session expired" } }, 401)));
    await expect(getCampaigns(identity)).rejects.toThrow("Session expired");
    expect(expired).toHaveBeenCalledWith("test-bearer");
  });

  it("never forwards a bearer token to a different origin", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    await expect(getJob(identity, "https://untrusted.invalid/job" )).rejects.toThrow();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("rejects unsupported fixture scenarios before creating an operation", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    await expect(startCheck(identity, "version", { scenario: "unverified-live" }))
      .rejects.toMatchObject({ code: "INVALID_FIXTURE_SCENARIO" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("rejects unsupported MIME types before requesting an upload capability", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    await expect(uploadSubmission(identity, { campaignId: "campaign", file: new File(["unsupported"], "draft.svg", { type: "image/svg+xml" }),
      caption: "Preserved caption", creatorId: "creator", rightsAttested: true, noticeVersion: "notice-v1", noticeAcknowledged: true }))
      .rejects.toMatchObject({ code: "UNSUPPORTED_MEDIA_TYPE" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("adds member credentials to the capability-authorized content upload", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(json({ upload_id: "upload-1", content_url: "/uploads/upload-1/content", upload_token: "one-time", finalize_token: "finalize" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(json({ asset_id: "asset-1" }))
      .mockResolvedValueOnce(json({ id: "submission-1", versions: [{ id: "version-1", version_number: 1 }] }));
    vi.stubGlobal("fetch", fetcher);
    await uploadSubmission(identity, { campaignId: "campaign-1", file: new File(["fixture"], "draft.mp4", { type: "video/mp4" }), caption: "Authorized draft", creatorId: "creator-1", rightsAttested: true, noticeVersion: "notice-v1", noticeAcknowledged: true });
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toMatchObject({ notice_version: "notice-v1", notice_acknowledged: true, purpose: "campaign_check", rights_attested: true });
    const contentHeaders = fetcher.mock.calls[1][1].headers;
    expect(contentHeaders).toMatchObject({ Authorization: "Bearer test-bearer", "X-Organization-Id": identity.organizationId, "X-Upload-Token": "one-time" });
    expect(contentHeaders).not.toHaveProperty("X-Fixture-User");
  });

  it("creates a scoped creator link without sending it or exposing a secret in the body", async () => {
    const invitationUrl = `http://127.0.0.1:3000/creator#invite=${"s".repeat(43)}`;
    const fetcher = vi.fn().mockResolvedValue(json({
      id: "grant-1",
      campaign_id: "campaign-1",
      creator_id: "creator-1",
      submission_id: "submission-1",
      allowed_actions: ["read_submission", "upload_source", "submit_version"],
      expires_at: "2026-10-28T12:00:00Z",
      invitation_url: invitationUrl,
    }, 201));
    vi.stubGlobal("fetch", fetcher);

    await expect(createGuestInvitation(identity, "campaign / one", {
      creatorId: "creator-1",
      recoveryId: "recovery-1",
    })).resolves.toMatchObject({ invitationUrl, submissionId: "submission-1" });
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][0]).toContain("/campaigns/campaign%20%2F%20one/guest-invitations");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
      creator_id: "creator-1",
      recovery_id: "recovery-1",
    });
    expect(fetcher.mock.calls[0][1].headers.get("Authorization")).toBe("Bearer test-bearer");
  });

  it("shares an explicit creator-feedback snapshot with idempotency and truthful provenance", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({
      id: "feedback-1",
      submission_id: "submission-1",
      submission_version_id: "version-1",
      analysis_id: "analysis-1",
      fix_request_draft_id: "draft-1",
      version_no: 1,
      message: "Replace the unsupported product claim.",
      start_ms: 1200,
      end_ms: 2400,
      invocation_mode: "fixture",
      analysis_status: "completed",
      manifest_hash: "a".repeat(64),
      historical: false,
      published_at: "2026-10-28T12:00:00Z",
    }, 201));
    vi.stubGlobal("fetch", fetcher);

    await expect(publishCreatorFeedback(identity, "analysis / one", {
      fixRequestDraftId: "draft-1",
      message: "Replace the unsupported product claim.",
      startMs: 1200,
      endMs: 2400,
    }, "feedback-command-1")).resolves.toMatchObject({
      id: "feedback-1",
      analysisId: "analysis-1",
      fixRequestDraftId: "draft-1",
      invocationMode: "fixture",
      analysisStatus: "completed",
      versionNo: 1,
      manifestHash: "a".repeat(64),
      historical: false,
    });
    expect(fetcher.mock.calls[0][0]).toContain("/checks/analysis%20%2F%20one/creator-feedback");
    expect(fetcher.mock.calls[0][1].headers.get("Idempotency-Key")).toBe("feedback-command-1");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
      fix_request_draft_id: "draft-1",
      message: "Replace the unsupported product claim.",
      start_ms: 1200,
      end_ms: 2400,
    });
  });

  it("rejects creator feedback when the API omits provenance", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({
      id: "feedback-1",
      submission_id: "submission-1",
      submission_version_id: "version-1",
      analysis_id: "analysis-1",
      fix_request_draft_id: "draft-1",
      version_no: 1,
      message: "Replace the unsupported product claim.",
      analysis_status: "completed",
      manifest_hash: "a".repeat(64),
      historical: false,
      published_at: "2026-10-28T12:00:00Z",
    }, 201)));

    await expect(publishCreatorFeedback(identity, "analysis-1", {
      fixRequestDraftId: "draft-1",
      message: "Replace the unsupported product claim.",
    }, "feedback-command-1")).rejects.toMatchObject({ code: "CREATOR_FEEDBACK_RESPONSE_INVALID" });
  });

  it("preserves partial deletion and destination status instead of claiming success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ id: "receipt", status: "partial",
      notice: "Cleanup is incomplete.", destinations: [{ destination: "supabase_storage", status: "retry_pending" }],
    }, 202)));
    const receipt = await requestDeletion(identity, { submissionId: "submission" });
    expect(receipt.status).toBe("partial");
    expect(receipt.destinations).toEqual([{ destination: "supabase_storage", status: "retry_pending" }]);
    expect(receipt.notice).toBe("Cleanup is incomplete.");
  });

  it("loads campaign-scoped durable receipts with their retry metadata", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ items: [{ id: "receipt", resource_type: "media_asset",
      resource_id: "asset", status: "failed", requested_by_kind: "retention", attempt_count: 3,
      max_attempts: 3, created_at: "2026-10-22T12:00:00Z", retry_after: null,
      last_error_code: "STORAGE_UNAVAILABLE", destinations: [{ destination: "supabase_storage", status: "retry_pending" }],
    }] }));
    vi.stubGlobal("fetch", fetcher);
    const receipts = await getDeletionRequests(identity, "campaign / one");
    expect(fetcher.mock.calls[0][0]).toContain("/deletion-requests?campaign_id=campaign%20%2F%20one");
    expect(receipts[0]).toMatchObject({ resourceType: "media_asset", resourceId: "asset", status: "failed",
      requestedByKind: "retention", attemptCount: 3, maxAttempts: 3, lastErrorCode: "STORAGE_UNAVAILABLE" });
    expect(receipts[0].retryAfter).toBeUndefined();
  });

  it("retries an expired media asset receipt without changing its resource type", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ id: "receipt", resource_type: "media_asset", resource_id: "asset", status: "completed" }, 202));
    vi.stubGlobal("fetch", fetcher);
    await requestDeletion(identity, { resourceType: "media_asset", resourceId: "asset" });
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ resource_type: "media_asset", resource_id: "asset" });
  });

  it("does not mistake a malformed response for verified empty deletion history", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({})));
    await expect(getDeletionRequests(identity, "campaign")).rejects.toThrow("Deletion history could not be verified");
  });

  it("reads decoded media mode independently from fixture provider execution", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ invocation_mode: "fixture", items: [], media_processing: {
      mode: "decoded", processor_version: "sandbox-v1",
    } })));
    expect(await getMediaProcessing(identity)).toEqual({ mode: "decoded", processorVersion: "sandbox-v1" });
  });

  it("does not assume fixture media mode when configuration is missing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ invocation_mode: "fixture", items: [] })));
    await expect(getMediaProcessing(identity)).rejects.toThrow("has not verified its media processing mode");
  });

  it("preserves measured processing snapshots without inventing metadata for legacy versions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ items: [{ id: "submission", versions: [
      { id: "version-2", version_no: 2, duration_ms: 2432, media_processing: { mode: "decoded", processor_version: "sandbox-v1",
        duration_ms: 2432, width: 640, height: 360, frame_rate: 24, audio_present: false, normalized_sha256: "a".repeat(64),
        source_time_mapping: { kind: "identity", source_origin_ms: 0, normalized_origin_ms: 0, precision_ms: 1 } } },
      { id: "version-1", version_no: 1, media_processing: {} },
    ] }] })));
    const [submission] = await getSubmissions(identity, "campaign");
    expect(submission.versions[0]).toMatchObject({ sourceDurationMs: 2432, mediaProcessing: { mode: "decoded", durationMs: 2432,
      width: 640, height: 360, audioPresent: false, sourceTimeMapping: { kind: "identity", sourceOriginMs: 0, normalizedOriginMs: 0, precisionMs: 1 } } });
    expect(submission.versions[1].mediaProcessing).toBeUndefined();
  });

  it("stops after a safe finalization rejection without creating a submission or fixture fallback", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(json({ upload_id: "upload-1", content_url: "/uploads/upload-1/content", upload_token: "one-time", finalize_token: "finalize" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(json({ error: { code: "MEDIA_INVALID", message: "The media could not be decoded within supported limits." } }, 422));
    vi.stubGlobal("fetch", fetcher);
    await expect(uploadSubmission(identity, { campaignId: "campaign", file: new File(["bad media"], "draft.mp4", { type: "video/mp4" }),
      caption: "Preserved caption", creatorId: "creator", rightsAttested: true, noticeVersion: "notice-v1", noticeAcknowledged: true })).rejects.toThrow("could not be decoded within supported limits");
    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(fetcher.mock.calls[2][0]).toContain("/uploads/upload-1/finalize");
  });

  it("fetches public notice content without bearer, tenant headers or credentials", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ version: "notice-v1", purpose: "campaign_check", title: "Workspace notice",
      body: "Local fixture processing.", notice_hash: "a".repeat(64), status: "draft_local_only", published_at: "2026-10-23T00:00:00Z" }));
    vi.stubGlobal("fetch", fetcher);
    expect(await getProcessingNotice()).toMatchObject({ version: "notice-v1", noticeHash: "a".repeat(64), status: "draft_local_only" });
    const init = fetcher.mock.calls[0][1];
    expect(init.headers.has("Authorization")).toBe(false);
    expect(init.headers.has("X-Organization-Id")).toBe(false);
    expect(init.credentials).toBe("omit");
    expect(init.cache).toBe("no-store");
  });

  it("rejects incomplete notice provenance instead of allowing implicit acceptance", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ version: "notice-v1", purpose: "campaign_check", body: "Incomplete." })));
    await expect(getProcessingNotice()).rejects.toThrow("could not be verified");
  });

  it("withdraws the exact scoped receipt without fabricating completed cleanup", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ id: "deletion", resource_type: "media_asset", resource_id: "asset",
      status: "partial", destinations: [{ destination: "supabase_storage", status: "retry_pending" }] }, 202));
    vi.stubGlobal("fetch", fetcher);
    expect(await withdrawProcessingAuthorization(identity, "receipt")).toMatchObject({ status: "partial", resourceType: "media_asset", resourceId: "asset" });
    expect(fetcher.mock.calls[0][0]).toContain("/consent-receipts/receipt/withdraw");
    expect(fetcher.mock.calls[0][1].method).toBe("POST");
    expect(fetcher.mock.calls[0][1].headers.get("X-Organization-Id")).toBe(identity.organizationId);
  });

  it("never turns legacy, missing or revoked receipt provenance into active authorization", async () => {
    const receipt = { id: "receipt", purpose: "campaign_check", notice_version: "notice-v1", notice_hash: "a".repeat(64), accepted_at: "2026-10-23T00:00:00Z" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ items: [{ id: "submission", versions: [
      { id: "legacy", version_no: 1, authorization_status: "legacy_no_notice", consent_receipt: null },
      { id: "missing", version_no: 2, authorization_status: "active", consent_receipt: null },
      { id: "revoked", version_no: 3, authorization_status: "active", consent_receipt: { ...receipt, revoked_at: "2026-10-23T00:01:00Z" } },
      { id: "active", version_no: 4, authorization_status: "active", consent_receipt: receipt },
    ] }] })));
    const [submission] = await getSubmissions(identity, "campaign");
    expect(Object.fromEntries(submission.versions.map((version) => [version.id, version.authorizationStatus])))
      .toEqual({ legacy: "legacy_no_notice", missing: "unknown", revoked: "revoked", active: "active" });
  });
});
