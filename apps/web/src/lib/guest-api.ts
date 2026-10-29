const DEFAULT_API_BASE_URL = "http://127.0.0.1:8010/api/v1";

const GUEST_API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL
).replace(/\/$/, "");

export const MAX_GUEST_UPLOAD_BYTES = 5_000_000;
export const GUEST_LINK_ENDED_MESSAGE =
  "This creator link has ended or is no longer available. Ask the brand team for a new link.";
export const GUEST_UNAVAILABLE_MESSAGE =
  "The creator portal could not be opened. Check your connection and try again.";

export type GuestAllowedAction = "read_submission" | "upload_source" | "submit_version";

export type GuestExchange = {
  status: "active";
  expires_at: string;
};

export type GuestProcessingNotice = {
  version: string;
  purpose: "campaign_check";
  title: string;
  body: string;
  notice_hash: string;
  status: "draft_local_only";
  published_at: string;
};

export type GuestSubmission = {
  session_expires_at: string;
  campaign: { name: string; market: string; brand_name: string };
  creator: { name: string; handle: string };
  submission: {
    current_version: null | { id: string; version_no: number; caption: string; created_at: string; consent_receipt_id: string | null };
    review_state: "awaiting_brand_review" | "changes_requested" | "approved";
    approved_version_no: number | null;
  };
  allowed_actions: GuestAllowedAction[];
  feedback: Array<{
    version_no: number;
    message: string;
    start_ms: number | null;
    end_ms: number | null;
    invocation_mode: "fixture" | "recorded" | "live";
    analysis_status: "queued" | "running" | "completed" | "partial" | "failed" | "cancelled";
    manifest_hash: string;
    published_at: string;
    historical: boolean;
  }>;
};

export type GuestWithdrawal = {
  id: string;
  status: "requested" | "in_progress" | "partial" | "completed" | "failed";
};

export type GuestDraftInput = {
  file: File;
  caption: string;
  expectedCurrentVersionId: string | null;
  expectedVersionNo: number;
  rightsAttested: true;
  noticeVersion: string;
  noticeAcknowledged: true;
  intentIdempotencyKey: string;
  versionIdempotencyKey: string;
};

type JsonRecord = Record<string, unknown>;
type GuestUploadIntent = {
  upload_id: string;
  content_url: string;
  upload_token: string;
  finalize_url: string;
  finalize_token: string;
  required_header: "X-Upload-Token";
  max_bytes: number;
  expires_at: string;
  authorization_status: "active";
  consent_receipt: {
    id: string;
    purpose: "campaign_check";
    notice_version: string;
    notice_hash: string;
    accepted_at: string;
  };
};

type GuestFinalizedAsset = { asset_id: string; status: "validated" };

const ACTIONABLE_STATUS = new Set([409, 413, 415, 422, 429]);
const ENDED_STATUS = new Set([401, 403, 404]);

export class GuestPortalError extends Error {
  readonly kind: "ended" | "unavailable";

  constructor(kind: "ended" | "unavailable") {
    super(kind === "ended" ? GUEST_LINK_ENDED_MESSAGE : GUEST_UNAVAILABLE_MESSAGE);
    this.name = "GuestPortalError";
    this.kind = kind;
  }
}

export class GuestActionError extends Error {
  readonly kind = "actionable" as const;
  readonly status: number;
  readonly code: string;
  readonly retryable: boolean;

  constructor(input: { status: number; code: string; message: string; retryable?: boolean }) {
    super(input.message);
    this.name = "GuestActionError";
    this.status = input.status;
    this.code = input.code;
    this.retryable = input.retryable ?? false;
  }
}

function isRecord(value: unknown): value is JsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(value: JsonRecord, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNonEmptyString(value: unknown): value is string {
  return isString(value) && value.length > 0;
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 1;
}

function isOptionalNonNegativeInteger(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isInteger(value) && value >= 0);
}

function isTimestamp(value: unknown): value is string {
  return isString(value)
    && /(?:Z|[+-]\d{2}:\d{2})$/.test(value)
    && Number.isFinite(Date.parse(value));
}

function isUuid(value: unknown): value is string {
  return isString(value)
    && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

function isSha256(value: unknown): value is string {
  return isString(value) && /^[0-9a-f]{64}$/i.test(value);
}

function parseExchange(value: unknown): GuestExchange {
  if (!isRecord(value)
    || !hasExactKeys(value, ["status", "expires_at"])
    || value.status !== "active"
    || !isTimestamp(value.expires_at)) {
    throw new GuestPortalError("unavailable");
  }
  return { status: "active", expires_at: value.expires_at };
}

function parseNotice(value: unknown): GuestProcessingNotice {
  if (!isRecord(value)
    || !hasExactKeys(value, ["version", "purpose", "title", "body", "notice_hash", "status", "published_at"])
    || !isNonEmptyString(value.version)
    || value.purpose !== "campaign_check"
    || !isNonEmptyString(value.title)
    || !isNonEmptyString(value.body)
    || !isSha256(value.notice_hash)
    || value.status !== "draft_local_only"
    || !isTimestamp(value.published_at)) {
    throw new GuestPortalError("unavailable");
  }
  return {
    version: value.version,
    purpose: "campaign_check",
    title: value.title,
    body: value.body,
    notice_hash: value.notice_hash,
    status: "draft_local_only",
    published_at: value.published_at,
  };
}

function parseAllowedActions(value: unknown): GuestAllowedAction[] {
  if (!Array.isArray(value)) throw new GuestPortalError("unavailable");
  const readOnly = value.length === 1 && value[0] === "read_submission";
  const mutation = value.length === 3
    && value[0] === "read_submission"
    && value[1] === "upload_source"
    && value[2] === "submit_version";
  if (!readOnly && !mutation) throw new GuestPortalError("unavailable");
  return [...value] as GuestAllowedAction[];
}

function parseSubmission(value: unknown): GuestSubmission {
  if (!isRecord(value)
    || !hasExactKeys(value, ["session_expires_at", "campaign", "creator", "submission", "allowed_actions", "feedback"])
    || !isTimestamp(value.session_expires_at)
    || !isRecord(value.campaign)
    || !hasExactKeys(value.campaign, ["name", "market", "brand_name"])
    || !isString(value.campaign.name)
    || !isString(value.campaign.market)
    || !isString(value.campaign.brand_name)
    || !isRecord(value.creator)
    || !hasExactKeys(value.creator, ["name", "handle"])
    || !isString(value.creator.name)
    || !isString(value.creator.handle)
    || !isRecord(value.submission)
    || !hasExactKeys(value.submission, ["current_version", "review_state", "approved_version_no"])
    || !["awaiting_brand_review", "changes_requested", "approved"].includes(String(value.submission.review_state))
    || !(value.submission.approved_version_no === null || isPositiveInteger(value.submission.approved_version_no))
    || !Array.isArray(value.feedback)) {
    throw new GuestPortalError("unavailable");
  }

  const version = value.submission.current_version;
  if (version !== null && (!isRecord(version)
    || !hasExactKeys(version, ["id", "version_no", "caption", "created_at", "consent_receipt_id"])
    || !isUuid(version.id)
    || !isPositiveInteger(version.version_no)
    || !isString(version.caption)
    || !(version.consent_receipt_id === null || isUuid(version.consent_receipt_id))
    || !isTimestamp(version.created_at))) {
    throw new GuestPortalError("unavailable");
  }

  const feedback = value.feedback.map((item) => {
    if (!isRecord(item)
      || !hasExactKeys(item, [
        "version_no", "message", "start_ms", "end_ms", "invocation_mode",
        "analysis_status", "manifest_hash", "published_at", "historical",
      ])
      || !isPositiveInteger(item.version_no)
      || !isNonEmptyString(item.message)
      || !isOptionalNonNegativeInteger(item.start_ms)
      || !isOptionalNonNegativeInteger(item.end_ms)
      || ((item.start_ms === null) !== (item.end_ms === null))
      || (item.start_ms !== null && item.end_ms !== null && item.end_ms <= item.start_ms)
      || !["fixture", "recorded", "live"].includes(String(item.invocation_mode))
      || !["queued", "running", "completed", "partial", "failed", "cancelled"].includes(String(item.analysis_status))
      || !isSha256(item.manifest_hash)
      || !isTimestamp(item.published_at)
      || typeof item.historical !== "boolean") {
      throw new GuestPortalError("unavailable");
    }
    return {
      version_no: item.version_no,
      message: item.message,
      start_ms: item.start_ms,
      end_ms: item.end_ms,
      invocation_mode: item.invocation_mode as GuestSubmission["feedback"][number]["invocation_mode"],
      analysis_status: item.analysis_status as GuestSubmission["feedback"][number]["analysis_status"],
      manifest_hash: item.manifest_hash,
      published_at: item.published_at,
      historical: item.historical,
    };
  });

  return {
    session_expires_at: value.session_expires_at,
    campaign: {
      name: value.campaign.name,
      market: value.campaign.market,
      brand_name: value.campaign.brand_name,
    },
    creator: { name: value.creator.name, handle: value.creator.handle },
    submission: {
      current_version: version === null ? null : {
        id: version.id as string,
        version_no: version.version_no as number,
        caption: version.caption as string,
        created_at: version.created_at as string,
        consent_receipt_id: version.consent_receipt_id as string | null,
      },
      review_state: value.submission.review_state as GuestSubmission["submission"]["review_state"],
      approved_version_no: value.submission.approved_version_no as number | null,
    },
    allowed_actions: parseAllowedActions(value.allowed_actions),
    feedback,
  };
}

function expectedGuestRoute(uploadId: string, operation: "content" | "finalize"): string {
  return `/api/v1/guest/uploads/${uploadId}/${operation}`;
}

function parseUploadIntent(value: unknown): GuestUploadIntent {
  if (!isRecord(value)
    || !hasExactKeys(value, [
      "upload_id", "content_url", "upload_token", "finalize_url", "finalize_token",
      "required_header", "max_bytes", "expires_at", "authorization_status", "consent_receipt",
    ])
    || !isUuid(value.upload_id)
    || value.content_url !== expectedGuestRoute(value.upload_id, "content")
    || !isNonEmptyString(value.upload_token)
    || value.upload_token.length > 500
    || value.finalize_url !== expectedGuestRoute(value.upload_id, "finalize")
    || !isNonEmptyString(value.finalize_token)
    || value.finalize_token.length > 500
    || value.required_header !== "X-Upload-Token"
    || value.max_bytes !== MAX_GUEST_UPLOAD_BYTES
    || !isTimestamp(value.expires_at)
    || value.authorization_status !== "active"
    || !isRecord(value.consent_receipt)
    || !hasExactKeys(value.consent_receipt, ["id", "purpose", "notice_version", "notice_hash", "accepted_at"])
    || !isUuid(value.consent_receipt.id)
    || value.consent_receipt.purpose !== "campaign_check"
    || !isNonEmptyString(value.consent_receipt.notice_version)
    || !isSha256(value.consent_receipt.notice_hash)
    || !isTimestamp(value.consent_receipt.accepted_at)) {
    throw new GuestPortalError("unavailable");
  }
  return value as GuestUploadIntent;
}

function parseUploadedContent(value: unknown, intent: GuestUploadIntent, expectedBytes: number): void {
  if (!isRecord(value)
    || !hasExactKeys(value, ["upload_id", "status", "received_bytes"])
    || value.upload_id !== intent.upload_id
    || value.status !== "content_uploaded"
    || value.received_bytes !== expectedBytes) {
    throw new GuestPortalError("unavailable");
  }
}

function parseFinalizedAsset(value: unknown): GuestFinalizedAsset {
  if (!isRecord(value)
    || !hasExactKeys(value, ["asset_id", "status"])
    || !isUuid(value.asset_id)
    || value.status !== "validated") {
    throw new GuestPortalError("unavailable");
  }
  return value as GuestFinalizedAsset;
}

function parseCreatedVersion(value: unknown, caption: string, expectedVersionNo: number): void {
  if (!isRecord(value)
    || !hasExactKeys(value, ["id", "version_no", "caption", "created_at"])
    || !isUuid(value.id)
    || value.version_no !== expectedVersionNo
    || value.caption !== caption
    || !isTimestamp(value.created_at)) {
    throw new GuestPortalError("unavailable");
  }
}

function guestUrl(path: string): string {
  if (!path.startsWith("/guest/") && !path.startsWith("/api/v1/guest/")) {
    throw new GuestPortalError("unavailable");
  }
  const base = new URL(GUEST_API_BASE_URL);
  return path.startsWith("/api/v1/guest/") ? `${base.origin}${path}` : `${GUEST_API_BASE_URL}${path}`;
}

function safeActionMessage(status: number): string {
  if (status === 409) return "This draft conflicts with newer upload state. Review the form and try again.";
  if (status === 413) return "The selected video is larger than the 5 MB upload limit.";
  if (status === 415) return "The video format could not be accepted. Choose an MP4 or WebM file.";
  if (status === 422) return "The draft could not be validated. Review the file, caption, and acknowledgments.";
  if (status === 429) return "This link has reached a temporary request limit. Wait before trying again.";
  return "The draft could not be submitted. Try again.";
}

async function responsePayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return undefined;
  return response.json().catch(() => undefined);
}

function actionError(response: Response, payload: unknown): GuestActionError {
  const envelope = isRecord(payload) ? payload : {};
  const error = isRecord(envelope.error) ? envelope.error : {};
  const code = isString(error.code) && /^[A-Z][A-Z0-9_]{1,79}$/.test(error.code)
    ? error.code
    : `HTTP_${response.status}`;
  const message = isString(error.message) && error.message.length > 0 && error.message.length <= 500
    ? error.message
    : safeActionMessage(response.status);
  return new GuestActionError({
    status: response.status,
    code,
    message,
    retryable: typeof error.retryable === "boolean" ? error.retryable : false,
  });
}

async function guestFetch(path: string, init: RequestInit, action = false): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (typeof init.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(guestUrl(path), {
      ...init,
      headers,
      cache: "no-store",
      credentials: "include",
      referrerPolicy: "no-referrer",
    });
  } catch (error) {
    if (init.signal?.aborted || (error instanceof DOMException && error.name === "AbortError")) throw error;
    if (action) {
      throw new GuestActionError({
        status: 0,
        code: "NETWORK_ERROR",
        message: "The upload was interrupted. Your draft is still here; check your connection and try again.",
        retryable: true,
      });
    }
    throw new GuestPortalError("unavailable");
  }

  if (!response.ok) {
    const payload = await responsePayload(response);
    if (ENDED_STATUS.has(response.status)) throw new GuestPortalError("ended");
    if (action && ACTIONABLE_STATUS.has(response.status)) throw actionError(response, payload);
    throw new GuestPortalError("unavailable");
  }
  return response;
}

async function guestJson<T>(
  path: string,
  init: RequestInit,
  parser: (value: unknown) => T,
  action = false,
): Promise<T> {
  const response = await guestFetch(path, init, action);
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) throw new GuestPortalError("unavailable");
  try {
    return parser(await response.json());
  } catch (error) {
    if (error instanceof GuestPortalError || error instanceof GuestActionError) throw error;
    throw new GuestPortalError("unavailable");
  }
}

export async function exchangeGuestInvitation(secret: string, signal?: AbortSignal): Promise<GuestExchange> {
  return guestJson("/guest/exchange", {
    method: "POST",
    body: JSON.stringify({ invitation_secret: secret }),
    signal,
  }, parseExchange);
}

export async function getGuestSubmission(signal?: AbortSignal): Promise<GuestSubmission> {
  return guestJson("/guest/submission", { method: "GET", signal }, parseSubmission);
}

export async function getGuestProcessingNotice(signal?: AbortSignal): Promise<GuestProcessingNotice> {
  return guestJson("/guest/notices/campaign-check", { method: "GET", signal }, parseNotice);
}

export async function withdrawGuestSource(receiptId: string): Promise<GuestWithdrawal> {
  if (!isUuid(receiptId)) throw new GuestPortalError("unavailable");
  return guestJson(`/guest/consent-receipts/${encodeURIComponent(receiptId)}/withdraw`, {
    method: "POST",
  }, (value) => {
    if (!isRecord(value)
      || !isUuid(value.id)
      || !["requested", "in_progress", "partial", "completed", "failed"].includes(String(value.status))) {
      throw new GuestPortalError("unavailable");
    }
    return { id: value.id, status: value.status as GuestWithdrawal["status"] };
  }, true);
}

export async function submitGuestDraft(input: GuestDraftInput): Promise<GuestSubmission> {
  const contentType = input.file.type;
  if (input.file.size === 0 || input.file.size > MAX_GUEST_UPLOAD_BYTES) {
    throw new GuestActionError({
      status: 413,
      code: "UPLOAD_SIZE_INVALID",
      message: "Choose a non-empty video up to 5 MB. Export a smaller MP4 or WebM before uploading.",
    });
  }
  if (contentType !== "video/mp4" && contentType !== "video/webm") {
    throw new GuestActionError({
      status: 415,
      code: "UNSUPPORTED_MEDIA_TYPE",
      message: "Select an MP4 or WebM video.",
    });
  }

  const intent = await guestJson("/guest/uploads", {
    method: "POST",
    headers: { "Idempotency-Key": input.intentIdempotencyKey },
    body: JSON.stringify({
      filename: input.file.name,
      content_type: contentType,
      byte_size: input.file.size,
      rights_attested: input.rightsAttested,
      notice_version: input.noticeVersion,
      notice_acknowledged: input.noticeAcknowledged,
      purpose: "campaign_check",
    }),
  }, parseUploadIntent, true);

  const uploadedResponse = await guestFetch(intent.content_url, {
    method: "PUT",
    headers: { "Content-Type": contentType, "X-Upload-Token": intent.upload_token },
    body: input.file,
  }, true);
  const uploadedType = uploadedResponse.headers.get("content-type") ?? "";
  if (!uploadedType.includes("application/json")) throw new GuestPortalError("unavailable");
  parseUploadedContent(await uploadedResponse.json(), intent, input.file.size);

  const finalized = await guestJson(intent.finalize_url, {
    method: "POST",
    body: JSON.stringify({ finalize_token: intent.finalize_token }),
  }, parseFinalizedAsset, true);

  await guestJson("/guest/submission-versions", {
    method: "POST",
    headers: { "Idempotency-Key": input.versionIdempotencyKey },
    body: JSON.stringify({
      asset_id: finalized.asset_id,
      caption: input.caption,
      expected_current_version_id: input.expectedCurrentVersionId,
    }),
  }, (value) => parseCreatedVersion(value, input.caption, input.expectedVersionNo), true);

  const authoritative = await getGuestSubmission();
  if (authoritative.submission.current_version === null) throw new GuestPortalError("unavailable");
  return authoritative;
}
