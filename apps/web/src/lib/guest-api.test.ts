import { afterEach, describe, expect, it, vi } from "vitest";

import {
  exchangeGuestInvitation,
  getGuestProcessingNotice,
  getGuestSubmission,
  GuestActionError,
  GuestPortalError,
  submitGuestDraft,
  withdrawGuestSource,
} from "@/lib/guest-api";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});

const submission = {
  session_expires_at: "2026-10-25T12:30:00Z",
  campaign: { name: "Autumn frames", market: "IN", brand_name: "Acme Eyewear" },
  creator: { name: "Riya", handle: "@riya" },
  submission: {
    current_version: { id: "33333333-3333-4333-8333-333333333333", version_no: 2, caption: "A measured caption", created_at: "2026-10-25T11:00:00Z", consent_receipt_id: "44444444-4444-4444-8444-444444444444" },
    review_state: "changes_requested",
    approved_version_no: null,
  },
  allowed_actions: ["read_submission"],
  feedback: [{
    version_no: 2,
    message: "Please hold the product for one more beat.",
    start_ms: 1200,
    end_ms: 2600,
    invocation_mode: "fixture",
    analysis_status: "completed",
    manifest_hash: "b".repeat(64),
    published_at: "2026-10-25T11:30:00Z",
    historical: false,
  }],
};

const notice = {
  version: "guest-notice-v1",
  purpose: "campaign_check",
  title: "Creator processing notice",
  body: "This source and its declared derivatives follow the stated retention process.",
  notice_hash: "a".repeat(64),
  status: "draft_local_only",
  published_at: "2026-10-25T10:30:00Z",
};

const uploadId = "11111111-1111-4111-8111-111111111111";
const receiptId = "22222222-2222-4222-8222-222222222222";
const versionId = "33333333-3333-4333-8333-333333333333";
const contentUrl = `/api/v1/guest/uploads/${uploadId}/content`;
const finalizeUrl = `/api/v1/guest/uploads/${uploadId}/finalize`;
const intent = {
  upload_id: uploadId,
  content_url: contentUrl,
  upload_token: "u".repeat(43),
  finalize_url: finalizeUrl,
  finalize_token: "f".repeat(43),
  required_header: "X-Upload-Token",
  max_bytes: 5_000_000,
  expires_at: "2026-10-25T10:35:00Z",
  authorization_status: "active",
  consent_receipt: {
    id: receiptId,
    purpose: "campaign_check",
    notice_version: notice.version,
    notice_hash: notice.notice_hash,
    accepted_at: "2026-10-25T10:30:01Z",
  },
};

describe("guest API transport", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses only the invitation secret and credentialed no-store guest transport", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ status: "active", expires_at: "2026-10-25T12:30:00Z" }));
    vi.stubGlobal("fetch", fetcher);

    await exchangeGuestInvitation("s".repeat(43));

    expect(fetcher).toHaveBeenCalledOnce();
    const [url, init] = fetcher.mock.calls[0];
    const headers = new Headers(init.headers);
    expect(url).toMatch(/\/api\/v1\/guest\/exchange$/);
    expect(init).toMatchObject({
      method: "POST",
      credentials: "include",
      cache: "no-store",
      referrerPolicy: "no-referrer",
    });
    expect(JSON.parse(init.body)).toEqual({ invitation_secret: "s".repeat(43) });
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.has("Authorization")).toBe(false);
    expect(headers.has("X-Organization-Id")).toBe(false);
  });

  it("accepts only the ordered read-only or mutation action allowlists", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(json(submission))
      .mockResolvedValueOnce(json({
        ...submission,
        submission: { current_version: null, review_state: "awaiting_brand_review", approved_version_no: null },
        allowed_actions: ["read_submission", "upload_source", "submit_version"],
      }));
    vi.stubGlobal("fetch", fetcher);

    await expect(getGuestSubmission()).resolves.toEqual(submission);
    await expect(getGuestSubmission()).resolves.toMatchObject({
      allowed_actions: ["read_submission", "upload_source", "submit_version"],
    });
  });

  it("fails closed on unknown submission authority or response fields", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(json({ ...submission, organization_id: "private-tenant" }))
      .mockResolvedValueOnce(json({ ...submission, allowed_actions: ["read_submission", "run_check"] }));
    vi.stubGlobal("fetch", fetcher);

    await expect(getGuestSubmission()).rejects.toMatchObject({ kind: "unavailable" });
    await expect(getGuestSubmission()).rejects.toMatchObject({ kind: "unavailable" });
  });

  it("fails closed when shared-feedback provenance or range is malformed", async () => {
    const feedback = submission.feedback[0];
    const fetcher = vi.fn()
      .mockResolvedValueOnce(json({
        ...submission,
        feedback: [{ ...feedback, invocation_mode: "unknown" }],
      }))
      .mockResolvedValueOnce(json({
        ...submission,
        feedback: [{ ...feedback, start_ms: 2600, end_ms: 1200 }],
      }));
    vi.stubGlobal("fetch", fetcher);

    await expect(getGuestSubmission()).rejects.toMatchObject({ kind: "unavailable" });
    await expect(getGuestSubmission()).rejects.toMatchObject({ kind: "unavailable" });
  });

  it("loads the exact guest-specific immutable notice", async () => {
    const fetcher = vi.fn().mockResolvedValue(json(notice));
    vi.stubGlobal("fetch", fetcher);
    await expect(getGuestProcessingNotice()).resolves.toEqual(notice);
    expect(fetcher.mock.calls[0][0]).toMatch(/\/api\/v1\/guest\/notices\/campaign-check$/);
  });

  it("withdraws only through the receipt-scoped guest route", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({
      id: "55555555-5555-4555-8555-555555555555",
      resource_type: "media_asset",
      resource_id: uploadId,
      status: "partial",
      destinations: [],
      requested_by_kind: "guest",
      attempt_count: 0,
      max_attempts: 3,
    }, 202));
    vi.stubGlobal("fetch", fetcher);

    await expect(withdrawGuestSource(receiptId)).resolves.toEqual({
      id: "55555555-5555-4555-8555-555555555555",
      status: "partial",
    });
    expect(fetcher.mock.calls[0][0]).toMatch(
      new RegExp(`/api/v1/guest/consent-receipts/${receiptId}/withdraw$`),
    );
    expect((fetcher.mock.calls[0][1] as RequestInit).method).toBe("POST");
  });

  it("performs the isolated guest upload flow and returns only the authoritative refetch", async () => {
    const file = new File(["video"], "creator.mp4", { type: "video/mp4" });
    const authoritative = {
      ...submission,
      submission: {
        current_version: { id: versionId, version_no: 1, caption: "Creator caption", created_at: "2026-10-25T10:31:00Z", consent_receipt_id: receiptId },
        review_state: "awaiting_brand_review",
        approved_version_no: null,
      },
    };
    const fetcher = vi.fn()
      .mockResolvedValueOnce(json(intent, 201))
      .mockResolvedValueOnce(json({ upload_id: uploadId, status: "content_uploaded", received_bytes: file.size }))
      .mockResolvedValueOnce(json({ asset_id: uploadId, status: "validated" }))
      .mockResolvedValueOnce(json({ id: versionId, version_no: 1, caption: "Creator caption", created_at: "2026-10-25T10:31:00Z" }, 201))
      .mockResolvedValueOnce(json(authoritative));
    vi.stubGlobal("fetch", fetcher);

    await expect(submitGuestDraft({
      file,
      caption: "Creator caption",
      expectedCurrentVersionId: null,
      expectedVersionNo: 1,
      rightsAttested: true,
      noticeVersion: notice.version,
      noticeAcknowledged: true,
      intentIdempotencyKey: "intent-key",
      versionIdempotencyKey: "version-key",
    })).resolves.toEqual(authoritative);

    expect(fetcher).toHaveBeenCalledTimes(5);
    const [intentRequest, contentRequest, finalizeRequest, versionRequest, refetchRequest] = fetcher.mock.calls;

    expect(intentRequest[0]).toMatch(/\/api\/v1\/guest\/uploads$/);
    expect(new Headers(intentRequest[1].headers).get("Idempotency-Key")).toBe("intent-key");
    const intentBody = JSON.parse(intentRequest[1].body);
    expect(intentBody).toEqual({
      filename: "creator.mp4",
      content_type: "video/mp4",
      byte_size: file.size,
      rights_attested: true,
      notice_version: notice.version,
      notice_acknowledged: true,
      purpose: "campaign_check",
    });

    expect(contentRequest[0]).toBe(`http://127.0.0.1:8010${contentUrl}`);
    expect(contentRequest[1].body).toBe(file);
    expect(new Headers(contentRequest[1].headers).get("X-Upload-Token")).toBe(intent.upload_token);
    expect(finalizeRequest[0]).toBe(`http://127.0.0.1:8010${finalizeUrl}`);
    expect(JSON.parse(finalizeRequest[1].body)).toEqual({ finalize_token: intent.finalize_token });

    expect(versionRequest[0]).toMatch(/\/api\/v1\/guest\/submission-versions$/);
    expect(new Headers(versionRequest[1].headers).get("Idempotency-Key")).toBe("version-key");
    expect(JSON.parse(versionRequest[1].body)).toEqual({
      asset_id: uploadId,
      caption: "Creator caption",
      expected_current_version_id: null,
    });
    expect(refetchRequest[0]).toMatch(/\/api\/v1\/guest\/submission$/);

    for (const [, request] of fetcher.mock.calls) {
      const headers = new Headers(request.headers);
      expect(headers.has("Authorization")).toBe(false);
      expect(headers.has("X-Organization-Id")).toBe(false);
      expect(headers.has("X-Fixture-User")).toBe(false);
      expect(request).toMatchObject({ credentials: "include", cache: "no-store" });
    }
    expect(JSON.stringify([intentBody, JSON.parse(versionRequest[1].body)]))
      .not.toMatch(/organization|campaign_id|creator_id|submission_id|object_key/i);
  });

  it("rejects a widened upload authorization before sending content", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ ...intent, object_key: "private/source" }, 201));
    vi.stubGlobal("fetch", fetcher);
    await expect(submitGuestDraft({
      file: new File(["video"], "creator.mp4", { type: "video/mp4" }),
      caption: "Caption",
      expectedCurrentVersionId: null,
      expectedVersionNo: 1,
      rightsAttested: true,
      noticeVersion: notice.version,
      noticeAcknowledged: true,
      intentIdempotencyKey: "intent-key",
      versionIdempotencyKey: "version-key",
    })).rejects.toMatchObject({ kind: "unavailable" });
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it.each([401, 403, 404])("returns the same safe ended state for guest status %s", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ error: { message: "raw grant state" } }, status)));
    await expect(getGuestSubmission()).rejects.toEqual(expect.objectContaining({
      name: "GuestPortalError",
      kind: "ended",
    } satisfies Partial<GuestPortalError>));
  });

  it.each([409, 413, 415, 422, 429])("keeps mutation status %s actionable and inline", async (status) => {
    const fetcher = vi.fn().mockResolvedValue(json({
      error: { code: "SAFE_GUEST_ERROR", message: "Review the draft and try again.", retryable: false },
    }, status));
    vi.stubGlobal("fetch", fetcher);
    await expect(submitGuestDraft({
      file: new File(["video"], "creator.mp4", { type: "video/mp4" }),
      caption: "Caption",
      expectedCurrentVersionId: null,
      expectedVersionNo: 1,
      rightsAttested: true,
      noticeVersion: notice.version,
      noticeAcknowledged: true,
      intentIdempotencyKey: "intent-key",
      versionIdempotencyKey: "version-key",
    })).rejects.toEqual(expect.objectContaining({
      name: "GuestActionError",
      kind: "actionable",
      status,
      code: "SAFE_GUEST_ERROR",
    } satisfies Partial<GuestActionError>));
  });
});
