import { AUTH_MODE, notifySessionExpired } from "@/lib/supabase";
import type { components } from "@/lib/generated/api";
import type {
  AcceptedOperation,
  ApprovalRecord,
  ApprovalReport,
  Campaign,
  CampaignBrief,
  CampaignReadiness,
  CampaignRequirement,
  CampaignRequirementKind,
  CampaignTrack,
  CatalogCreator,
  CatalogProduct,
  Capability,
  Check,
  CheckComparison,
  ComparisonItem,
  ConsentReceipt,
  CoverageItem,
  CreatorFeedback,
  DeletionReceipt,
  Finding,
  FindingDecision,
  FixtureIdentity,
  FixRequestDraft,
  GuestInvitation,
  InvocationMode,
  Job,
  MediaProcessing,
  MediaProcessingMetadata,
  ProcessingNotice,
  ProductClaim,
  Role,
  RulePackVersion,
  Submission,
  SubmissionVersion,
  TrackEnvironmentSummary,
  TrackEvent,
  TrackEventKind,
  Workspace,
} from "@/lib/types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8010/api/v1";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL
).replace(/\/$/, "");

const ACME_ORGANIZATION_ID = "11111111-1111-4111-8111-111111111111";
const BETA_ORGANIZATION_ID = "22222222-2222-4222-8222-222222222222";

/**
 * Seed identities are intentionally data, not authorization. The API derives the
 * actual membership and roles for the selected user.
 */
export const FIXTURE_IDENTITIES: FixtureIdentity[] = [
  {
    key: "acme-marketer",
    label: "Maya — marketer",
    hint: "Create campaigns, upload drafts and start checks",
    user: "marketer@vouch.test",
    organizationId: ACME_ORGANIZATION_ID,
    organizationLabel: "Acme Eyewear",
  },
  {
    key: "acme-reviewer",
    label: "Rohan — reviewer",
    hint: "Decide findings, request changes and approve",
    user: "reviewer@vouch.test",
    organizationId: ACME_ORGANIZATION_ID,
    organizationLabel: "Acme Eyewear",
  },
  {
    key: "acme-admin",
    label: "Avery — admin only",
    hint: "Workspace administration; reviewer authority is separate",
    user: "admin@vouch.test",
    organizationId: ACME_ORGANIZATION_ID,
    organizationLabel: "Acme Eyewear",
  },
  {
    key: "acme-viewer",
    label: "Vihaan — viewer",
    hint: "Read-only workspace access",
    user: "viewer@vouch.test",
    organizationId: ACME_ORGANIZATION_ID,
    organizationLabel: "Acme Eyewear",
  },
  {
    key: "beta-member",
    label: "Beta member — separate tenant",
    hint: "Demonstrates organization isolation",
    user: "beta@vouch.test",
    organizationId: BETA_ORGANIZATION_ID,
    organizationLabel: "Beta Outdoors",
  },
];

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryable: boolean;
  readonly requestId?: string;

  constructor(input: {
    message: string;
    code?: string;
    status?: number;
    retryable?: boolean;
    requestId?: string;
  }) {
    super(input.message);
    this.name = "ApiError";
    this.code = input.code ?? "REQUEST_FAILED";
    this.status = input.status ?? 0;
    this.retryable = input.retryable ?? false;
    this.requestId = input.requestId;
  }
}

type JsonRecord = Record<string, unknown>;
type ApiSchemas = components["schemas"];
export type StorageUsage = ApiSchemas["StorageUsageResponse"];
export const MAX_UPLOAD_BYTES = 5_000_000;

function record(value: unknown): JsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : {};
}

function valueAt(source: JsonRecord, ...keys: string[]): unknown {
  for (const key of keys) {
    if (source[key] !== undefined && source[key] !== null) return source[key];
  }
  return undefined;
}

function stringAt(source: JsonRecord, keys: string[], fallback = ""): string {
  const value = valueAt(source, ...keys);
  return typeof value === "string" || typeof value === "number"
    ? String(value)
    : fallback;
}

function numberAt(source: JsonRecord, keys: string[], fallback = 0): number {
  const value = valueAt(source, ...keys);
  return typeof value === "number"
    ? value
    : typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))
      ? Number(value)
      : fallback;
}

function booleanAt(source: JsonRecord, keys: string[], fallback = false): boolean {
  const value = valueAt(source, ...keys);
  return typeof value === "boolean" ? value : fallback;
}

function arrayAt(source: JsonRecord, ...keys: string[]): unknown[] {
  const value = valueAt(source, ...keys);
  return Array.isArray(value) ? value : [];
}

function unwrapItems(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  const source = record(value);
  return arrayAt(source, "items", "results", "data");
}

function normalizeRole(value: unknown): Role | undefined {
  const role = String(value).toLowerCase();
  return ["admin", "marketer", "reviewer", "viewer"].includes(role)
    ? (role as Role)
    : undefined;
}

export function buildFixtureHeaders(identity: FixtureIdentity): Record<string, string> {
  return {
    "X-Organization-Id": identity.organizationId,
    "X-Fixture-User": identity.user,
  };
}

export function buildIdentityHeaders(
  identity: FixtureIdentity,
  organizationRequired = true,
): Record<string, string> {
  if (AUTH_MODE === "fixture") return buildFixtureHeaders(identity);
  if (AUTH_MODE !== "supabase" || !identity.accessToken) {
    throw new ApiError({ status: 401, code: "SESSION_REQUIRED", message: "Sign in to continue." });
  }
  if (organizationRequired && !identity.organizationId) {
    throw new ApiError({ code: "WORKSPACE_REQUIRED", message: "Select an active workspace to continue." });
  }
  return {
    Authorization: `Bearer ${identity.accessToken}`,
    ...(organizationRequired ? { "X-Organization-Id": identity.organizationId } : {}),
  };
}

function apiUrl(pathOrUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl)) {
    if (AUTH_MODE === "supabase" && new URL(pathOrUrl).origin !== new URL(API_BASE_URL).origin) {
      throw new ApiError({ code: "UNTRUSTED_API_URL", message: "The API returned an unsupported request destination." });
    }
    return pathOrUrl;
  }
  const normalizedPath = pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`;
  if (API_BASE_URL.startsWith("/")) {
    return `${API_BASE_URL}${normalizedPath}`;
  }
  const base = new URL(API_BASE_URL);
  if (normalizedPath === base.pathname || normalizedPath.startsWith(`${base.pathname}/`)) {
    return `${base.origin}${normalizedPath}`;
  }
  return `${API_BASE_URL}${normalizedPath}`;
}

async function requestJson(
  identity: FixtureIdentity | undefined,
  pathOrUrl: string,
  init: RequestInit = {},
  organizationRequired = true,
): Promise<unknown> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  for (const [key, value] of Object.entries(identity ? buildIdentityHeaders(identity, organizationRequired) : {})) {
    headers.set(key, value);
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(apiUrl(pathOrUrl), { ...init, headers });
  } catch (error) {
    if (init.signal?.aborted || (error instanceof DOMException && error.name === "AbortError")) {
      throw new DOMException("The request was aborted.", "AbortError");
    }
    throw new ApiError({
      code: "NETWORK_ERROR",
      message:
        error instanceof Error
          ? `Could not reach the Vouch API. ${error.message}`
          : "Could not reach the Vouch API.",
      retryable: true,
    });
  }

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => ({}))
    : await response.text().catch(() => "");

  if (!response.ok) {
    if (response.status === 401 && identity) notifySessionExpired(identity.accessToken);
    const envelope = record(payload);
    const error = record(envelope.error);
    throw new ApiError({
      status: response.status,
      code: stringAt(error, ["code"], `HTTP_${response.status}`),
      message: stringAt(
        error,
        ["message"],
        typeof payload === "string" && payload ? payload : "The request could not be completed.",
      ),
      retryable: booleanAt(error, ["retryable"], response.status >= 500),
      requestId: stringAt(error, ["request_id", "requestId"]) || undefined,
    });
  }
  return payload;
}

function normalizeWorkspace(input: unknown): Workspace {
  const source = record(input);
  const membership = record(source.membership);
  const rawRoles = [
    ...arrayAt(source, "roles"),
    ...arrayAt(membership, "roles"),
    ...arrayAt(source, "membership_roles"),
  ];
  const roles = rawRoles
    .map((role) => normalizeRole(typeof role === "object" ? valueAt(record(role), "role", "name") : role))
    .filter((role): role is Role => Boolean(role));
  return {
    id: stringAt(source, ["id", "organization_id", "workspace_id"]),
    name: stringAt(source, ["name", "organization_name", "workspace_name"], "Workspace"),
    roles: [...new Set(roles)],
    membershipStatus: stringAt(
      membership,
      ["status", "membership_status"],
      stringAt(source, ["membership_status"], "active"),
    ),
  };
}

function normalizeRulePack(input: unknown): Campaign["pinnedRulePack"] {
  const source = record(input);
  if (Object.keys(source).length === 0) return undefined;
  return {
    id: stringAt(source, ["id", "rule_pack_version_id"]) || undefined,
    name: stringAt(source, ["name", "rule_pack_name", "title"], "Campaign review pack"),
    version: stringAt(source, ["version", "version_no", "label"], "Unversioned"),
    reviewStatus: stringAt(source, ["review_status", "status"], "draft"),
  };
}

function normalizeCampaign(input: unknown): Campaign {
  const source = record(input);
  const product = record(valueAt(source, "product", "product_snapshot"));
  const rule =
    valueAt(source, "pinned_rule_pack", "rule_pack", "rule_pack_version") ??
    arrayAt(source, "pinned_rule_packs", "rule_pack_versions")[0];
  return {
    id: stringAt(source, ["id", "campaign_id"]),
    name: stringAt(source, ["name", "campaign_name"], "Untitled campaign"),
    objective: stringAt(source, ["objective", "description"], "No objective recorded"),
    market: stringAt(source, ["market", "market_code", "country"], "Unknown market"),
    brandName: stringAt(source, ["brand_name", "brand"], stringAt(product, ["name"], "Workspace brand")),
    productName:
      stringAt(product, ["name", "title"]) || stringAt(source, ["product_name"]) || undefined,
    productId: stringAt(product, ["id"]) || undefined,
    creatorIds: arrayAt(source, "creator_ids").map(String),
    status: stringAt(source, ["status"], "draft"),
    createdAt: stringAt(source, ["created_at", "createdAt"]) || undefined,
    currentActions: arrayAt(source, "current_actions", "actions")
      .map((action) =>
        typeof action === "string"
          ? action
          : stringAt(record(action), ["label", "name", "action"]),
      )
      .filter(Boolean)
      .concat(numberAt(source, ["submission_count"]) === 0 ? ["Upload an authorized draft"] : []),
    pinnedRulePack: normalizeRulePack(rule),
  };
}

const CAPABILITY_DETAILS: Record<string, { family: string; role: string }> = {
  spark: { family: "Spark", role: "Visual reasoning and rule-mapped Check evidence" },
  reasoner: { family: "Spark", role: "Visual reasoning and rule-mapped Check evidence" },
  voice: { family: "Voice Transcribe", role: "Timestamped speech evidence" },
  transcriber: { family: "Voice Transcribe", role: "Timestamped speech evidence" },
  sam: { family: "SAM", role: "Product and concept evidence with sampling limits" },
  segmenter: { family: "SAM", role: "Product and concept evidence with sampling limits" },
  image: { family: "Image", role: "Conditional eyewear preview outside restricted regions" },
  try_on: { family: "Image", role: "Conditional eyewear preview outside restricted regions" },
  wonder: { family: "Wonder", role: "Bounded, cited campaign evidence dossier" },
  dossier: { family: "Wonder", role: "Bounded, cited campaign evidence dossier" },
};

function normalizeCapability(input: unknown, index: number): Capability {
  const source = record(input);
  const key = stringAt(source, ["family", "capability", "name", "id"], `capability-${index}`);
  const normalizedKey = key.toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
  const details =
    Object.entries(CAPABILITY_DETAILS).find(([candidate]) => normalizedKey.includes(candidate))?.[1];
  return {
    id: stringAt(source, ["id"], normalizedKey),
    family: details?.family ?? key,
    role: stringAt(source, ["role", "purpose", "description"], details?.role ?? "Planned capability"),
    status: stringAt(source, ["status", "capability_status"], "not_configured") as Capability["status"],
    reason: stringAt(source, ["reason", "status_reason", "message"], "No readiness reason supplied"),
    market: stringAt(source, ["market", "market_code"]) || undefined,
    invocationMode:
      (stringAt(source, ["invocation_mode"]) as InvocationMode) || undefined,
    policyVersion: stringAt(source, ["policy_version"]) || undefined,
  };
}

function normalizeMediaProcessing(input: unknown): MediaProcessingMetadata | undefined {
  const source = record(input);
  if (source.mode !== "fixture" && source.mode !== "decoded") return undefined;
  const mapping = record(source.source_time_mapping);
  return {
    mode: source.mode,
    processorVersion: stringAt(source, ["processor_version"]) || undefined,
    durationMs: numberAt(source, ["duration_ms"]) || undefined,
    width: numberAt(source, ["width"]) || undefined,
    height: numberAt(source, ["height"]) || undefined,
    frameRate: numberAt(source, ["frame_rate"]) || undefined,
    audioPresent: typeof source.audio_present === "boolean" ? source.audio_present : undefined,
    normalizedSha256: stringAt(source, ["normalized_sha256"]) || undefined,
    sourceTimeMapping: mapping.kind === "identity"
      && typeof mapping.source_origin_ms === "number" && typeof mapping.normalized_origin_ms === "number"
      ? { kind: "identity", sourceOriginMs: mapping.source_origin_ms, normalizedOriginMs: mapping.normalized_origin_ms,
        precisionMs: typeof mapping.precision_ms === "number" ? mapping.precision_ms : undefined }
      : undefined,
  };
}

function normalizeVersion(input: unknown, index: number): SubmissionVersion {
  const source = record(input);
  const analysis = record(valueAt(source, "latest_check", "latest_analysis", "analysis"));
  const checks = arrayAt(source, "checks");
  const latestCheck = record(checks[0]);
  const receipt = normalizeConsentReceipt(source.consent_receipt);
  const authorizationStatus = source.authorization_status === "revoked" || receipt?.revokedAt ? "revoked"
    : source.authorization_status === "active" && receipt ? "active"
    : source.authorization_status === "legacy_no_notice" ? "legacy_no_notice" : "unknown";
  return {
    id: stringAt(source, ["id", "submission_version_id", "version_id"]),
    versionNo: numberAt(source, ["version_no", "version", "number"], index + 1),
    caption: stringAt(source, ["caption", "caption_text"]),
    createdAt: stringAt(source, ["created_at", "uploaded_at"]) || undefined,
    uploader: stringAt(source, ["uploader", "uploaded_by", "uploader_email"]) || undefined,
    mediaHash: stringAt(source, ["media_hash", "content_hash", "source_hash"]) || undefined,
    captionHash: stringAt(source, ["caption_hash"]) || undefined,
    assetName: stringAt(source, ["asset_name", "file_name", "filename"]) || undefined,
    sourceDurationMs: numberAt(source, ["source_duration_ms", "duration_ms"]) || undefined,
    mediaProcessing: normalizeMediaProcessing(valueAt(source, "media_processing", "processing_metadata")),
    authorizationStatus,
    consentReceipt: receipt,
    latestCheckId:
      stringAt(source, ["latest_check_id", "check_id", "analysis_id"]) ||
      stringAt(analysis, ["id", "check_id", "analysis_id"]) ||
      stringAt(latestCheck, ["id", "check_id", "analysis_id"]) ||
      undefined,
    superseded: booleanAt(source, ["superseded"], false),
  };
}

function normalizeConsentReceipt(input: unknown): ConsentReceipt | undefined {
  const source = record(input);
  if (!source.id || source.purpose !== "campaign_check" || !source.notice_version || !source.accepted_at
    || typeof source.notice_hash !== "string" || !/^[a-f0-9]{64}$/i.test(source.notice_hash)) return undefined;
  return {
    id: stringAt(source, ["id"]), purpose: "campaign_check",
    noticeVersion: stringAt(source, ["notice_version"]), noticeHash: stringAt(source, ["notice_hash"]),
    acceptedAt: stringAt(source, ["accepted_at"]), revokedAt: stringAt(source, ["revoked_at"]) || undefined,
    actorUserId: stringAt(source, ["actor_user_id"]) || undefined,
    revocationActorKind: stringAt(source, ["revocation_actor_kind"]) || undefined,
    revocationReason: stringAt(source, ["revocation_reason"]) || undefined,
  };
}

export function processingNoticeUrl(version: string): string {
  return apiUrl(`/notices/campaign-check/${encodeURIComponent(version)}`);
}

export async function getProcessingNotice(signal?: AbortSignal): Promise<ProcessingNotice> {
  const source = record(await requestJson(undefined, "/notices/campaign-check", { signal, credentials: "omit", cache: "no-store" }, false));
  if (source.purpose !== "campaign_check" || source.status !== "draft_local_only"
    || typeof source.version !== "string" || !source.version || typeof source.body !== "string" || !source.body
    || typeof source.title !== "string" || !source.title || typeof source.published_at !== "string"
    || typeof source.notice_hash !== "string" || !/^[a-f0-9]{64}$/i.test(source.notice_hash)) {
    throw new ApiError({ code: "NOTICE_UNAVAILABLE", message: "The current processing notice could not be verified. Uploads are unavailable." });
  }
  return { version: source.version, purpose: "campaign_check", noticeHash: source.notice_hash,
    body: source.body, title: source.title, status: "draft_local_only", publishedAt: source.published_at };
}

function normalizeSubmission(input: unknown): Submission {
  const source = record(input);
  const versions = arrayAt(source, "versions", "submission_versions").map(normalizeVersion);
  if (versions.length === 0 && valueAt(source, "version_no", "submission_version_id")) {
    versions.push(normalizeVersion(source, 0));
  }
  versions.sort((a, b) => b.versionNo - a.versionNo);
  return {
    id: stringAt(source, ["id", "submission_id"]),
    campaignId: stringAt(source, ["campaign_id"]),
    creatorName: stringAt(source, ["creator_name", "creator", "submitted_by"], "Authorized creator"),
    creatorId: stringAt(source, ["creator_id"]),
    versions,
    currentVersionId:
      stringAt(source, ["current_version_id", "latest_version_id"]) || versions[0]?.id,
  };
}

function normalizeDecision(input: unknown): FindingDecision | undefined {
  const source = record(input);
  if (Object.keys(source).length === 0) return undefined;
  return {
    action: stringAt(source, ["action", "decision"]) as FindingDecision["action"],
    rationale: stringAt(source, ["rationale", "reason"]),
    actor: stringAt(source, ["actor", "actor_email", "reviewer"]) || undefined,
    decidedAt: stringAt(source, ["decided_at", "created_at", "timestamp"]) || undefined,
  };
}

function normalizeFinding(input: unknown, index: number): Finding {
  const source = record(input);
  const timeRange = record(valueAt(source, "source_time_range", "time_range", "timestamp_range"));
  const span = record(valueAt(source, "caption_span"));
  const rule = record(valueAt(source, "rule", "rule_version"));
  const decisions = arrayAt(source, "decisions", "finding_decisions");
  const decision = valueAt(source, "decision", "latest_decision") ?? decisions.at(-1);
  return {
    id: stringAt(source, ["id", "finding_id"], `finding-${index + 1}`),
    title: stringAt(source, ["title", "issue", "summary"], "Potential issue"),
    severity: stringAt(source, ["severity"], "minor") as Finding["severity"],
    ruleId:
      stringAt(source, ["rule_id"]) || stringAt(rule, ["id", "rule_id"], "Rule unavailable"),
    ruleVersion:
      stringAt(source, ["rule_version", "rule_version_id"]) ||
      stringAt(rule, ["version", "version_id"], "Unversioned"),
    ruleLabel: stringAt(source, ["rule_label", "rule_type"], stringAt(rule, ["label", "type"], "Draft policy")),
    modality: stringAt(source, ["modality", "evidence_source", "source"], "unknown"),
    startMs:
      numberAt(source, ["start_ms"], numberAt(timeRange, ["start_ms"], -1)) >= 0
        ? numberAt(source, ["start_ms"], numberAt(timeRange, ["start_ms"]))
        : undefined,
    endMs:
      numberAt(source, ["end_ms"], numberAt(timeRange, ["end_ms"], -1)) >= 0
        ? numberAt(source, ["end_ms"], numberAt(timeRange, ["end_ms"]))
        : undefined,
    captionSpan:
      Object.keys(span).length > 0
        ? { start: numberAt(span, ["start"]), end: numberAt(span, ["end"]) }
        : undefined,
    timingPrecision: stringAt(source, ["timing_precision", "precision"]) || undefined,
    evidenceText: stringAt(source, ["evidence_text", "evidence", "description", "quote"], "Evidence excerpt unavailable"),
    uncertainty: stringAt(source, ["uncertainty", "confidence_provenance"], "Not calibrated"),
    suggestedAction: stringAt(source, ["suggested_action", "suggestion", "next_action"], "Review this evidence"),
    sourceUrl: stringAt(source, ["source_url", "rule_source_url"]) || undefined,
    decision: normalizeDecision(decision),
  };
}

function normalizeCoverage(input: unknown, required: string[]): CoverageItem[] {
  if (Array.isArray(input)) {
    return input.map((item) => {
      if (typeof item === "string") {
        return { modality: item, status: "complete" as const, detail: "Evidence available" };
      }
      const source = record(item);
      return {
        modality: stringAt(source, ["modality", "name", "type"], "unknown"),
        status: stringAt(source, ["status", "coverage_status"], "unknown") as CoverageItem["status"],
        detail: stringAt(source, ["detail", "message", "reason"], "No detail supplied"),
      };
    });
  }
  const source = record(input);
  const items = Object.entries(source).map(([modality, raw]) => {
    if (typeof raw === "boolean") {
      return {
        modality,
        status: raw ? ("complete" as const) : ("missing" as const),
        detail: raw ? "Evidence available" : "Required evidence unavailable",
      };
    }
    if (typeof raw === "string") {
      const status = ["complete", "partial", "missing", "unknown"].includes(raw)
        ? (raw as CoverageItem["status"])
        : "unknown";
      return { modality, status, detail: raw };
    }
    const item = record(raw);
    return {
      modality,
      status: stringAt(item, ["status"], "unknown") as CoverageItem["status"],
      detail: stringAt(item, ["detail", "reason"], "No detail supplied"),
    };
  });
  return items.length > 0
    ? items
    : required.map((modality) => ({ modality, status: "unknown", detail: "No coverage report returned" }));
}

function normalizeApproval(input: unknown, index: number): ApprovalRecord {
  const source = record(input);
  return {
    id: stringAt(source, ["id", "approval_id"], `approval-${index + 1}`),
    versionNo: numberAt(source, ["version_no", "submission_version_no"]) || undefined,
    reviewStatus: stringAt(source, ["review_status", "action", "status"], "approved") as ApprovalRecord["reviewStatus"],
    reviewer: stringAt(source, ["reviewer", "reviewer_user_id", "actor", "actor_email"], "Unknown reviewer"),
    decidedAt: stringAt(source, ["decided_at", "created_at", "timestamp"]),
    rationale: stringAt(source, ["rationale", "reason"]) || undefined,
    manifestHash: stringAt(source, ["manifest_hash"]) || undefined,
    submissionVersionId: stringAt(source, ["submission_version_id"]) || undefined,
  };
}

function normalizeApprovalReport(input: unknown): ApprovalReport {
  const source = record(input);
  const modelVersions = record(valueAt(source, "model_versions"));
  return {
    reportVersion: stringAt(source, ["report_version"]) as ApprovalReport["reportVersion"],
    exportedAt: stringAt(source, ["exported_at"]),
    currentStatus: stringAt(source, ["current_status"]) as ApprovalReport["currentStatus"],
    approvalId: stringAt(source, ["approval_id"]),
    analysisId: stringAt(source, ["analysis_id"]),
    campaignId: stringAt(source, ["campaign_id"]),
    campaignName: stringAt(source, ["campaign_name"]),
    submissionVersionId: stringAt(source, ["submission_version_id"]),
    submissionVersionNo: numberAt(source, ["submission_version_no"]),
    rulePackVersionId: stringAt(source, ["rule_pack_version_id"]),
    manifestHash: stringAt(source, ["manifest_hash"]),
    mediaHash: stringAt(source, ["media_hash"]),
    captionHash: stringAt(source, ["caption_hash"]),
    reviewerUserId: stringAt(source, ["reviewer_user_id"]),
    reviewerDisplayName: stringAt(source, ["reviewer_display_name"], "Unknown reviewer"),
    approvedAt: stringAt(source, ["approved_at"]),
    approvalRationale: stringAt(source, ["approval_rationale"]),
    invocationMode: stringAt(source, ["invocation_mode"]) as ApprovalReport["invocationMode"],
    analysisStatus: stringAt(source, ["analysis_status"]) as ApprovalReport["analysisStatus"],
    schemaVersion: stringAt(source, ["schema_version"]),
    promptVersion: stringAt(source, ["prompt_version"]),
    modelVersions: Object.fromEntries(
      Object.entries(modelVersions).filter((entry): entry is [string, string] => typeof entry[1] === "string"),
    ),
    requiredCoverage: arrayAt(source, "required_coverage").map(String),
    observedCoverage: arrayAt(source, "observed_coverage").map(String),
    evidence: arrayAt(source, "evidence").map((item) => {
      const evidence = record(item);
      const startMs = numberAt(evidence, ["start_ms"], -1);
      const endMs = numberAt(evidence, ["end_ms"], -1);
      return {
        id: stringAt(evidence, ["id"]),
        modality: stringAt(evidence, ["modality"]),
        startMs: startMs >= 0 ? startMs : undefined,
        endMs: endMs >= 0 ? endMs : undefined,
        precision: stringAt(evidence, ["precision"]),
        description: stringAt(evidence, ["description"]),
        capturedAt: stringAt(evidence, ["captured_at"]),
      };
    }),
    findings: arrayAt(source, "findings").map((item) => {
      const finding = record(item);
      const startMs = numberAt(finding, ["start_ms"], -1);
      const endMs = numberAt(finding, ["end_ms"], -1);
      return {
        id: stringAt(finding, ["id"]),
        ruleId: stringAt(finding, ["rule_id"]),
        ruleVersion: stringAt(finding, ["rule_version"]),
        severity: stringAt(finding, ["severity"]),
        evidenceIds: arrayAt(finding, "evidence_ids").map(String),
        startMs: startMs >= 0 ? startMs : undefined,
        endMs: endMs >= 0 ? endMs : undefined,
        evidenceText: stringAt(finding, ["evidence_text"]),
        uncertainty: stringAt(finding, ["uncertainty"]),
        suggestedAction: stringAt(finding, ["suggested_action"]),
        decision: stringAt(finding, ["decision"]) as ApprovalReport["findings"][number]["decision"],
        decisionRationale: stringAt(finding, ["decision_rationale"]),
        decisionActorUserId: stringAt(finding, ["decision_actor_user_id"]),
        decidedAt: stringAt(finding, ["decided_at"]),
      };
    }),
    limitations: arrayAt(source, "limitations").map(String),
  };
}

function normalizeCheck(input: unknown): Check {
  const outer = record(input);
  const source = record(valueAt(outer, "check", "analysis") ?? outer);
  const review = record(valueAt(source, "review", "review_context"));
  const failure = record(valueAt(source, "failure", "error"));
  const requiredCoverage = arrayAt(source, "required_coverage").map(String);
  const rawCoverage = valueAt(source, "observed_coverage", "coverage");
  return {
    id: stringAt(source, ["id", "check_id", "analysis_id"]),
    submissionVersionId: stringAt(source, ["submission_version_id", "version_id"]),
    analysisStatus: stringAt(source, ["analysis_status", "status"], "queued") as Check["analysisStatus"],
    machineAssessment: stringAt(source, ["machine_assessment", "assessment"], "not_assessed") as Check["machineAssessment"],
    reviewStatus: stringAt(source, ["review_status"], stringAt(review, ["status"], "unreviewed")) as Check["reviewStatus"],
    invocationMode: stringAt(source, ["invocation_mode"], "fixture") as InvocationMode,
    manifestHash: stringAt(source, ["manifest_hash"]),
    reviewVersion: numberAt(source, ["review_version", "expected_review_version"], numberAt(review, ["version"], 1)),
    scenario: stringAt(source, ["scenario", "fixture_scenario"]) || undefined,
    createdAt: stringAt(source, ["created_at", "started_at"]) || undefined,
    completedAt: stringAt(source, ["completed_at", "result_timestamp"]) || undefined,
    rulePackName: stringAt(source, ["rule_pack_name"], "Campaign review pack"),
    rulePackVersion: stringAt(source, ["rule_pack_version", "rule_pack_version_id"], "Pinned version"),
    promptVersion: stringAt(source, ["prompt_version"]) || undefined,
    modelVersion: stringAt(source, ["model_version", "model_id"]) || undefined,
    requiredCoverage,
    coverage: normalizeCoverage(rawCoverage, requiredCoverage),
    evidence: arrayAt(source, "evidence").map((item) => {
      const evidence = record(item);
      return {
        id: stringAt(evidence, ["id"]),
        modality: stringAt(evidence, ["modality"], "unknown"),
        startMs: numberAt(evidence, ["start_ms"], -1) >= 0 ? numberAt(evidence, ["start_ms"]) : undefined,
        endMs: numberAt(evidence, ["end_ms"], -1) >= 0 ? numberAt(evidence, ["end_ms"]) : undefined,
        precision: stringAt(evidence, ["precision"], "unknown"),
        description: stringAt(evidence, ["description"], "Evidence captured"),
        capturedAt: stringAt(evidence, ["captured_at"]) || undefined,
      };
    }),
    missingIntervals: arrayAt(source, "missing_intervals").map((item) => {
      const gap = record(item);
      return {
        modality: stringAt(gap, ["modality", "source"], "unknown"),
        startMs: numberAt(gap, ["start_ms"], -1) >= 0 ? numberAt(gap, ["start_ms"]) : undefined,
        endMs: numberAt(gap, ["end_ms"], -1) >= 0 ? numberAt(gap, ["end_ms"]) : undefined,
        reason: stringAt(gap, ["reason", "message"], "Evidence unavailable"),
      };
    }),
    findings: arrayAt(source, "findings").map(normalizeFinding),
    approvals: [valueAt(source, "approval"), ...arrayAt(source, "approvals", "review_events")]
      .filter(Boolean)
      .filter((item) => {
        const event = record(item);
        const action = stringAt(event, ["action", "review_status", "status"]);
        return ["approved", "rejected", "changes_requested", "revoked"].includes(action)
          || Boolean(stringAt(event, ["manifest_hash"]) && stringAt(event, ["submission_version_id"]));
      })
      .map(normalizeApproval),
    failure:
      Object.keys(failure).length > 0
        ? {
            code: stringAt(failure, ["code"], "CHECK_FAILED"),
            message: stringAt(failure, ["message"], "The check did not complete."),
            retryable: booleanAt(failure, ["retryable"]),
          }
        : undefined,
  };
}

function normalizeAccepted(input: unknown): AcceptedOperation {
  const source = record(input);
  return {
    operationId: stringAt(source, ["operation_id", "job_id", "id"]),
    resourceId: stringAt(source, ["resource_id", "check_id", "analysis_id"]),
    status: stringAt(source, ["status"], "queued"),
    statusUrl: stringAt(source, ["status_url"]),
    invocationMode: stringAt(source, ["invocation_mode"], "fixture") as InvocationMode,
  };
}

function normalizeJob(input: unknown): Job {
  const source = record(input);
  const result = record(valueAt(source, "result", "resource"));
  const failure = record(valueAt(source, "failure", "error"));
  return {
    id: stringAt(source, ["id", "job_id", "operation_id"]),
    status: stringAt(source, ["job_status", "status"], "queued") as Job["status"],
    stage: stringAt(source, ["stage", "current_stage", "stage_label"]) || undefined,
    attemptCount: numberAt(source, ["attempt_count", "attempt"], 0),
    retryAt: stringAt(source, ["retry_at", "retry_after"]) || undefined,
    resourceId:
      stringAt(source, ["resource_id", "check_id", "analysis_id"]) ||
      stringAt(result, ["id", "resource_id", "check_id"]) ||
      undefined,
    resultId: stringAt(source, ["result_id"]) || stringAt(result, ["id"]) || undefined,
    message:
      stringAt(source, ["message", "status_message"]) || stringAt(failure, ["message"]) || undefined,
    retryable: booleanAt(source, ["retryable"], booleanAt(failure, ["retryable"])) || undefined,
  };
}

export async function getWorkspaces(identity: FixtureIdentity, signal?: AbortSignal): Promise<Workspace[]> {
  return unwrapItems(await requestJson(identity, "/me/workspaces", { signal }, false)).map(normalizeWorkspace);
}

export async function getStorageUsage(identity: FixtureIdentity, signal?: AbortSignal): Promise<StorageUsage> {
  const source = record(await requestJson(identity, "/storage/usage", { signal }));
  const fields = ["limit_bytes", "used_bytes", "reserved_bytes", "pending_cleanup_bytes", "available_bytes", "max_upload_bytes"] as const;
  if (fields.some((field) => typeof source[field] !== "number" || !Number.isSafeInteger(source[field]) || Number(source[field]) < 0)
    || !["supabase", "database"].includes(String(source.storage_backend))) {
    throw new ApiError({ code: "STORAGE_USAGE_UNAVAILABLE", message: "Storage usage is unavailable. Refresh to try again." });
  }
  const usage: StorageUsage = {
    limit_bytes: Number(source.limit_bytes), used_bytes: Number(source.used_bytes),
    reserved_bytes: Number(source.reserved_bytes), pending_cleanup_bytes: Number(source.pending_cleanup_bytes),
    available_bytes: Number(source.available_bytes), max_upload_bytes: Number(source.max_upload_bytes),
    storage_backend: source.storage_backend === "supabase" ? "supabase" : "database",
  };
  const charged = usage.used_bytes + usage.reserved_bytes + usage.pending_cleanup_bytes;
  if (!Number.isSafeInteger(charged) || usage.limit_bytes <= 0 || usage.max_upload_bytes <= 0
    || usage.available_bytes !== Math.max(0, usage.limit_bytes - charged)) {
    throw new ApiError({ code: "STORAGE_USAGE_UNAVAILABLE", message: "Storage usage is unavailable. Refresh to try again." });
  }
  return usage;
}

export async function getCampaigns(identity: FixtureIdentity, signal?: AbortSignal): Promise<Campaign[]> {
  return unwrapItems(await requestJson(identity, "/campaigns", { signal })).map(normalizeCampaign);
}

export async function getCampaign(identity: FixtureIdentity, campaignId: string, signal?: AbortSignal): Promise<Campaign> {
  return normalizeCampaign(await requestJson(identity, `/campaigns/${campaignId}`, { signal }));
}

export async function getCampaignReadiness(
  identity: FixtureIdentity,
  campaignId: string,
  signal?: AbortSignal,
): Promise<CampaignReadiness> {
  const source = record(await requestJson(
    identity,
    `/campaigns/${encodeURIComponent(campaignId)}/readiness`,
    { signal },
  ));
  return {
    campaignId: stringAt(source, ["campaign_id"]),
    generationMode: stringAt(source, ["generation_mode"]) as CampaignReadiness["generationMode"],
    ready: booleanAt(source, ["ready"]),
    blockerCount: numberAt(source, ["blocker_count"]),
    actionCount: numberAt(source, ["action_count"]),
    summary: stringAt(source, ["summary"]),
    items: arrayAt(source, "items").map((item) => {
      const row = record(item);
      const citation = record(valueAt(row, "citation"));
      return {
        id: stringAt(row, ["id"]),
        severity: stringAt(row, ["severity"]) as CampaignReadiness["items"][number]["severity"],
        category: stringAt(row, ["category"]) as CampaignReadiness["items"][number]["category"],
        title: stringAt(row, ["title"]),
        detail: stringAt(row, ["detail"]),
        actionLabel: stringAt(row, ["action_label"]),
        citation: {
          sourceType: stringAt(citation, ["source_type"]) as CampaignReadiness["items"][number]["citation"]["sourceType"],
          sourceId: stringAt(citation, ["source_id"]),
          label: stringAt(citation, ["label"]),
          href: stringAt(citation, ["href"]),
        },
      };
    }),
    limitations: arrayAt(source, "limitations").map(String),
  };
}

function normalizeProductClaim(input: unknown): ProductClaim {
  const source = record(input);
  return {
    id: stringAt(source, ["id"]),
    productId: stringAt(source, ["product_id"]),
    approvedWording: stringAt(source, ["approved_wording"]),
    evidenceLabel: stringAt(source, ["evidence_label"]),
    evidenceUri: stringAt(source, ["evidence_uri"]),
    expiresAt: stringAt(source, ["expires_at"]) || undefined,
    status: stringAt(source, ["status"]) as ProductClaim["status"],
    createdAt: stringAt(source, ["created_at"]),
  };
}

function normalizeCampaignRequirement(input: unknown): CampaignRequirement {
  const source = record(input);
  return {
    id: stringAt(source, ["id"]),
    campaignId: stringAt(source, ["campaign_id"]),
    kind: stringAt(source, ["kind"]) as CampaignRequirement["kind"],
    label: stringAt(source, ["label"]),
    expectedText: stringAt(source, ["expected_text"]) || undefined,
    claimId: stringAt(source, ["claim_id"]) || undefined,
    required: booleanAt(source, ["required"]),
    createdAt: stringAt(source, ["created_at"]),
  };
}

export async function getCampaignBrief(
  identity: FixtureIdentity,
  campaignId: string,
  signal?: AbortSignal,
): Promise<CampaignBrief> {
  const source = record(await requestJson(
    identity,
    `/campaigns/${encodeURIComponent(campaignId)}/brief`,
    { signal },
  ));
  return {
    campaignId: stringAt(source, ["campaign_id"]),
    claims: arrayAt(source, "claims").map(normalizeProductClaim),
    requirements: arrayAt(source, "requirements").map(normalizeCampaignRequirement),
    assessments: arrayAt(source, "assessments").map((item) => {
      const assessment = record(item);
      return {
        requirementId: stringAt(assessment, ["requirement_id"]),
        submissionId: stringAt(assessment, ["submission_id"]) || undefined,
        submissionVersionId: stringAt(assessment, ["submission_version_id"]) || undefined,
        analysisId: stringAt(assessment, ["analysis_id"]) || undefined,
        status: stringAt(assessment, ["status"]) as CampaignBrief["assessments"][number]["status"],
        detail: stringAt(assessment, ["detail"]),
        evidenceIds: arrayAt(assessment, "evidence_ids").map(String),
      };
    }),
    limitations: arrayAt(source, "limitations").map(String),
  };
}

export async function createProductClaim(
  identity: FixtureIdentity,
  productId: string,
  input: {
    approvedWording: string;
    evidenceLabel: string;
    evidenceUri: string;
    expiresAt?: string;
  },
): Promise<ProductClaim> {
  return normalizeProductClaim(await requestJson(
    identity,
    `/products/${encodeURIComponent(productId)}/claims`,
    {
      method: "POST",
      body: JSON.stringify({
        approved_wording: input.approvedWording,
        evidence_label: input.evidenceLabel,
        evidence_uri: input.evidenceUri,
        expires_at: input.expiresAt,
      }),
    },
  ));
}

export async function createCampaignRequirement(
  identity: FixtureIdentity,
  campaignId: string,
  input: {
    kind: CampaignRequirementKind;
    label: string;
    expectedText?: string;
    claimId?: string;
  },
): Promise<CampaignRequirement> {
  return normalizeCampaignRequirement(await requestJson(
    identity,
    `/campaigns/${encodeURIComponent(campaignId)}/requirements`,
    {
      method: "POST",
      body: JSON.stringify({
        kind: input.kind,
        label: input.label,
        expected_text: input.expectedText,
        claim_id: input.claimId,
        required: true,
      }),
    },
  ));
}

function normalizeTrackSummary(input: unknown): TrackEnvironmentSummary {
  const source = record(input);
  const rawTotals = record(valueAt(source, "totals_by_currency"));
  const totalsByCurrency = Object.fromEntries(
    Object.entries(rawTotals).map(([currency, value]) => {
      const row = record(value);
      return [currency, {
        grossMinor: numberAt(row, ["gross_minor"]),
        refundedMinor: numberAt(row, ["refunded_minor"]),
        netMinor: numberAt(row, ["net_minor"]),
      }];
    }),
  );
  const conversionRate = valueAt(source, "conversion_rate");
  return {
    clicks: numberAt(source, ["clicks"]),
    orders: numberAt(source, ["orders"]),
    refunds: numberAt(source, ["refunds"]),
    conversionRate: typeof conversionRate === "number" ? conversionRate : undefined,
    totalsByCurrency,
  };
}

function normalizeTrackEvent(input: unknown): TrackEvent {
  const source = record(input);
  return {
    id: stringAt(source, ["id"]),
    creatorId: stringAt(source, ["creator_id"]),
    eventKind: stringAt(source, ["event_kind"]) as TrackEvent["eventKind"],
    environment: stringAt(source, ["environment"]) as TrackEvent["environment"],
    externalEventId: stringAt(source, ["external_event_id"]),
    orderExternalId: stringAt(source, ["order_external_id"]) || undefined,
    amountMinor: numberAt(source, ["amount_minor"]),
    currency: stringAt(source, ["currency"]),
    attributionStatus: stringAt(source, ["attribution_status"]) as TrackEvent["attributionStatus"],
    attributionMethod: stringAt(source, ["attribution_method"]),
    occurredAt: stringAt(source, ["occurred_at"]),
    receivedAt: stringAt(source, ["received_at"]),
  };
}

export async function getCampaignTrack(
  identity: FixtureIdentity,
  campaignId: string,
  signal?: AbortSignal,
): Promise<CampaignTrack> {
  const source = record(await requestJson(
    identity,
    `/campaigns/${encodeURIComponent(campaignId)}/track`,
    { signal },
  ));
  return {
    campaignId: stringAt(source, ["campaign_id"]),
    freshnessAt: stringAt(source, ["freshness_at"]) || undefined,
    test: normalizeTrackSummary(source.test),
    live: normalizeTrackSummary(source.live),
    events: arrayAt(source, "events").map(normalizeTrackEvent),
  };
}

export async function recordTestOutcomeEvent(
  identity: FixtureIdentity,
  campaignId: string,
  input: {
    creatorId: string;
    eventKind: TrackEventKind;
    externalEventId: string;
    orderExternalId?: string;
    amountMinor?: number;
    currency?: string;
    occurredAt: string;
  },
): Promise<TrackEvent> {
  return normalizeTrackEvent(await requestJson(
    identity,
    `/campaigns/${encodeURIComponent(campaignId)}/track/test-events`,
    {
      method: "POST",
      body: JSON.stringify({
        creator_id: input.creatorId,
        event_kind: input.eventKind,
        external_event_id: input.externalEventId,
        order_external_id: input.orderExternalId,
        amount_minor: input.amountMinor ?? 0,
        currency: input.currency ?? "INR",
        occurred_at: input.occurredAt,
      }),
    },
  ));
}

export async function createCampaign(
  identity: FixtureIdentity,
  input: {
    name: string;
    objective: string;
    market: string;
    productId: string;
    rulePackVersionId: string;
    creatorIds: string[];
  },
): Promise<Campaign> {
  return normalizeCampaign(
    await requestJson(identity, "/campaigns", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        name: input.name,
        objective: input.objective,
        market: input.market,
        product_id: input.productId,
        rule_pack_version_id: input.rulePackVersionId,
        creator_ids: input.creatorIds,
      } satisfies ApiSchemas["CampaignCreate"]),
    }),
  );
}

export async function createGuestInvitation(
  identity: FixtureIdentity,
  campaignId: string,
  input: { creatorId: string; recoveryId: string; submissionId?: string },
): Promise<GuestInvitation> {
  const source = record(await requestJson(
    identity,
    `/campaigns/${encodeURIComponent(campaignId)}/guest-invitations`,
    {
      method: "POST",
      body: JSON.stringify({
        creator_id: input.creatorId,
        recovery_id: input.recoveryId,
        ...(input.submissionId ? { submission_id: input.submissionId } : {}),
      }),
    },
  ));
  const actions = arrayAt(source, "allowed_actions").map(String);
  if (
    !stringAt(source, ["id"])
    || !stringAt(source, ["campaign_id"])
    || !stringAt(source, ["creator_id"])
    || !stringAt(source, ["submission_id"])
    || !stringAt(source, ["expires_at"])
    || !stringAt(source, ["invitation_url"])
    || actions.some((action) => !["read_submission", "upload_source", "submit_version"].includes(action))
    || !actions.includes("read_submission")
  ) {
    throw new ApiError({
      code: "GUEST_INVITATION_UNAVAILABLE",
      message: "The creator link response could not be verified. Try again.",
    });
  }
  return {
    id: stringAt(source, ["id"]),
    campaignId: stringAt(source, ["campaign_id"]),
    creatorId: stringAt(source, ["creator_id"]),
    submissionId: stringAt(source, ["submission_id"]),
    allowedActions: actions as GuestInvitation["allowedActions"],
    expiresAt: stringAt(source, ["expires_at"]),
    invitationUrl: stringAt(source, ["invitation_url"]),
  };
}

export async function getCatalog(
  identity: FixtureIdentity,
  signal?: AbortSignal,
): Promise<{
  products: CatalogProduct[];
  creators: CatalogCreator[];
  rulePacks: RulePackVersion[];
}> {
  const [productsPayload, creatorsPayload, packsPayload] = await Promise.all([
    requestJson(identity, "/products", { signal }),
    requestJson(identity, "/creators", { signal }),
    requestJson(identity, "/rule-pack-versions", { signal }),
  ]);
  return {
    products: unwrapItems(productsPayload).map((item) => {
      const row = record(item);
      return { id: stringAt(row, ["id"]), name: stringAt(row, ["name"]), sku: stringAt(row, ["sku"]) };
    }),
    creators: unwrapItems(creatorsPayload).map((item) => {
      const row = record(item);
      return {
        id: stringAt(row, ["id"]),
        name: stringAt(row, ["name"]),
        handle: stringAt(row, ["handle"]),
        rightsStatus: stringAt(row, ["rights_status"], "unknown"),
      };
    }),
    rulePacks: unwrapItems(packsPayload).map((item) => {
      const row = record(item);
      return {
        id: stringAt(row, ["id"]),
        name: stringAt(row, ["name"]),
        version: stringAt(row, ["version"]),
        status: stringAt(row, ["status"], "draft"),
      };
    }),
  };
}

export type CreatorMatchKind = "category_relevance" | "exact_product" | "unreviewed";

export interface CreatorEvidence {
  id: string;
  productId?: string;
  category: string;
  matchKind: CreatorMatchKind;
  sourceUri?: string;
  sourceLabel: string;
  proofKind: string;
  permissionStatus: string;
  verificationStatus: string;
  evidenceMode: string;
  description: string;
  capturedAt?: string;
  startMs?: number;
  endMs?: number;
}

export interface FindCreator extends CatalogCreator {
  evidenceTimestamp?: string;
  evidence: CreatorEvidence[];
}

function normalizeCreatorEvidence(input: unknown, index: number): CreatorEvidence {
  const source = record(input);
  const rawMatchKind = stringAt(source, ["match_kind"]);
  const matchKind: CreatorMatchKind =
    rawMatchKind === "exact_product" || rawMatchKind === "category_relevance"
      ? rawMatchKind
      : "unreviewed";
  const startMs = numberAt(source, ["start_ms"], -1);
  const endMs = numberAt(source, ["end_ms"], -1);
  return {
    id: stringAt(source, ["id"], `evidence-${index}`),
    productId: stringAt(source, ["product_id"]) || undefined,
    category: stringAt(source, ["category"], "Uncategorized"),
    matchKind,
    sourceUri: stringAt(source, ["source_uri"]) || undefined,
    sourceLabel: stringAt(source, ["source_label"], "Source not recorded"),
    proofKind: stringAt(source, ["proof_kind"], "Unspecified proof"),
    permissionStatus: stringAt(source, ["permission_status"], "unknown"),
    verificationStatus: stringAt(source, ["verification_status"], "unreviewed"),
    evidenceMode: stringAt(source, ["evidence_mode"], "unknown"),
    description: stringAt(source, ["description"], "No proof description recorded."),
    capturedAt: stringAt(source, ["captured_at", "evidence_timestamp"]) || undefined,
    startMs: startMs >= 0 ? startMs : undefined,
    endMs: endMs >= 0 ? endMs : undefined,
  };
}

function normalizeFindCreator(input: unknown): FindCreator {
  const source = record(input);
  const evidenceRows = arrayAt(source, "evidence", "proof_assets");
  const directEvidence = stringAt(source, ["match_kind"]) ? [source] : [];
  return {
    id: stringAt(source, ["id"]),
    name: stringAt(source, ["name"], "Unnamed creator"),
    handle: stringAt(source, ["handle"]),
    rightsStatus: stringAt(source, ["rights_status"], "unknown"),
    evidenceTimestamp: stringAt(source, ["evidence_timestamp"]) || undefined,
    evidence: (evidenceRows.length ? evidenceRows : directEvidence).map(normalizeCreatorEvidence),
  };
}

export async function getFindCreators(
  identity: FixtureIdentity,
  filters: { query?: string; category?: string; matchKind?: Exclude<CreatorMatchKind, "unreviewed"> } = {},
  signal?: AbortSignal,
): Promise<FindCreator[]> {
  const query = new URLSearchParams();
  if (filters.query?.trim()) query.set("q", filters.query.trim());
  if (filters.category) query.set("category", filters.category);
  if (filters.matchKind) query.set("match_kind", filters.matchKind);
  const suffix = query.size ? `?${query}` : "";
  return unwrapItems(await requestJson(identity, `/creators${suffix}`, { signal })).map(
    normalizeFindCreator,
  );
}

export async function addCreatorToCampaign(
  identity: FixtureIdentity,
  campaignId: string,
  creatorId: string,
  evidenceId: string,
): Promise<{
  id: string;
  campaignId: string;
  creatorId: string;
  evidenceId: string;
  created: boolean;
}> {
  const payload = await requestJson(
    identity,
    `/campaigns/${encodeURIComponent(campaignId)}/creators`,
    {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        creator_id: creatorId,
        evidence_id: evidenceId,
      } satisfies ApiSchemas["CampaignCreatorCreate"]),
    },
  );
  const source = record(payload);
  return {
    id: stringAt(source, ["id"]),
    campaignId: stringAt(source, ["campaign_id"]),
    creatorId: stringAt(source, ["creator_id"]),
    evidenceId: stringAt(source, ["evidence_id"]),
    created: booleanAt(source, ["created"]),
  };
}

export async function getCapabilities(
  identity: FixtureIdentity,
  market: string,
  signal?: AbortSignal,
): Promise<Capability[]> {
  const query = new URLSearchParams({ market });
  return unwrapItems(await requestJson(identity, `/capabilities?${query}`, { signal })).map(
    normalizeCapability,
  );
}

export async function getMediaProcessing(identity: FixtureIdentity, signal?: AbortSignal): Promise<MediaProcessing> {
  const source = record(await requestJson(identity, "/capabilities", { signal }));
  const processing = normalizeMediaProcessing(source.media_processing);
  if (!processing) {
    throw new ApiError({ code: "MEDIA_MODE_UNAVAILABLE", message: "The API has not verified its media processing mode. Refresh the campaign to retry." });
  }
  return { mode: processing.mode, processorVersion: processing.processorVersion };
}

export async function getSubmissions(
  identity: FixtureIdentity,
  campaignId: string,
  signal?: AbortSignal,
): Promise<Submission[]> {
  return unwrapItems(
    await requestJson(identity, `/campaigns/${campaignId}/submissions`, { signal }),
  ).map(normalizeSubmission);
}

export async function getCheck(identity: FixtureIdentity, checkId: string, signal?: AbortSignal): Promise<Check> {
  return normalizeCheck(await requestJson(identity, `/checks/${checkId}`, { signal }));
}

export async function getApprovalReport(
  identity: FixtureIdentity,
  checkId: string,
): Promise<ApprovalReport> {
  return normalizeApprovalReport(
    await requestJson(identity, `/checks/${checkId}/approval-report`),
  );
}

export async function startCheck(
  identity: FixtureIdentity,
  versionId: string,
  input: { scenario: string; rulePackVersionIds?: string[] },
): Promise<AcceptedOperation> {
  const supportedScenarios = [
    "success", "clean", "partial_voice", "transient_then_success", "invalid_output", "provider_down",
  ] as const satisfies readonly NonNullable<ApiSchemas["CheckCreate"]["scenario"]>[];
  const scenario = supportedScenarios.find((value) => value === input.scenario);
  if (!scenario) {
    throw new ApiError({ code: "INVALID_FIXTURE_SCENARIO", message: "Choose a supported fixture scenario before starting a Check." });
  }
  return normalizeAccepted(
    await requestJson(identity, `/submission-versions/${versionId}/checks`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        scenario,
        invocation_mode: "fixture",
        schema_version: "check-result.v1",
      } satisfies ApiSchemas["CheckCreate"]),
    }),
  );
}

export async function getJob(identity: FixtureIdentity, statusUrl: string, signal?: AbortSignal): Promise<Job> {
  return normalizeJob(await requestJson(identity, statusUrl, { signal }));
}

export async function decideFinding(
  identity: FixtureIdentity,
  findingId: string,
  input: { action: FindingDecision["action"]; rationale: string; expectedReviewVersion: number },
): Promise<void> {
  await requestJson(identity, `/findings/${findingId}/decisions`, {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({
      decision: input.action,
      rationale: input.rationale,
      expected_review_version: input.expectedReviewVersion,
    } satisfies ApiSchemas["FindingDecisionCreate"]),
  });
}

export async function makeReviewDecision(
  identity: FixtureIdentity,
  check: Check,
  input: { action: "approve" | "reject" | "request_changes" | "revoke"; rationale: string },
): Promise<Check> {
  const payload = await requestJson(identity, `/checks/${check.id}/review-decisions`, {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({
      action: input.action,
      rationale: input.rationale,
      manifest_hash: check.manifestHash,
      expected_review_version: check.reviewVersion,
    } satisfies ApiSchemas["ReviewDecisionCreate"]),
  });
  const source = record(payload);
  if (valueAt(source, "check", "analysis_status", "check_id")) return normalizeCheck(payload);
  return getCheck(identity, check.id);
}

export async function prepareFixRequest(
  identity: FixtureIdentity,
  checkId: string,
  findingIds: string[],
): Promise<FixRequestDraft> {
  const source = record(
    await requestJson(identity, `/checks/${checkId}/fix-request-drafts`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ finding_ids: findingIds } satisfies ApiSchemas["FixRequestCreate"]),
    }),
  );
  return {
    id: stringAt(source, ["id", "draft_id"]) || undefined,
    message: stringAt(source, ["text", "message", "body", "draft_text"]),
    createdAt: stringAt(source, ["created_at"]) || undefined,
    sent: false,
  };
}

function normalizeCreatorFeedback(value: unknown): CreatorFeedback {
  const source = record(value);
  const required = {
    id: stringAt(source, ["id"]),
    submissionId: stringAt(source, ["submission_id"]),
    submissionVersionId: stringAt(source, ["submission_version_id"]),
    analysisId: stringAt(source, ["analysis_id"]),
    fixRequestDraftId: stringAt(source, ["fix_request_draft_id"]),
    message: stringAt(source, ["message"]),
    manifestHash: stringAt(source, ["manifest_hash"]),
    publishedAt: stringAt(source, ["published_at"]),
  };
  const versionNo = valueAt(source, "version_no");
  const invocationMode = valueAt(source, "invocation_mode");
  const analysisStatus = valueAt(source, "analysis_status");
  const historical = valueAt(source, "historical");
  const startMs = valueAt(source, "start_ms");
  const endMs = valueAt(source, "end_ms");
  const validInvocationModes: InvocationMode[] = ["fixture", "recorded", "live"];
  const validAnalysisStatuses: CreatorFeedback["analysisStatus"][] = [
    "queued", "running", "completed", "partial", "failed", "cancelled",
  ];
  const validRange = startMs === undefined && endMs === undefined
    || typeof startMs === "number" && Number.isInteger(startMs) && startMs >= 0
      && typeof endMs === "number" && Number.isInteger(endMs) && endMs > startMs;

  if (
    Object.values(required).some((item) => !item)
    || typeof versionNo !== "number"
    || !Number.isInteger(versionNo)
    || versionNo < 1
    || typeof invocationMode !== "string"
    || !validInvocationModes.includes(invocationMode as InvocationMode)
    || typeof analysisStatus !== "string"
    || !validAnalysisStatuses.includes(analysisStatus as CreatorFeedback["analysisStatus"])
    || typeof historical !== "boolean"
    || !validRange
  ) {
    throw new ApiError({
      code: "CREATOR_FEEDBACK_RESPONSE_INVALID",
      message: "The shared creator feedback response could not be verified.",
    });
  }

  return {
    ...required,
    versionNo,
    startMs: typeof startMs === "number" ? startMs : undefined,
    endMs: typeof endMs === "number" ? endMs : undefined,
    invocationMode: invocationMode as InvocationMode,
    analysisStatus: analysisStatus as CreatorFeedback["analysisStatus"],
    historical,
  };
}

export async function publishCreatorFeedback(
  identity: FixtureIdentity,
  checkId: string,
  input: {
    fixRequestDraftId: string;
    message: string;
    startMs?: number;
    endMs?: number;
  },
  idempotencyKey = crypto.randomUUID(),
): Promise<CreatorFeedback> {
  const message = input.message.trim();
  const hasStart = input.startMs !== undefined;
  const hasEnd = input.endMs !== undefined;
  if (
    !input.fixRequestDraftId
    || !message
    || hasStart !== hasEnd
    || hasStart && (
      !Number.isInteger(input.startMs)
      || !Number.isInteger(input.endMs)
      || input.startMs! < 0
      || input.endMs! <= input.startMs!
    )
  ) {
    throw new ApiError({
      code: "CREATOR_FEEDBACK_INVALID",
      message: "Review the creator-visible message and timestamp range before sharing it.",
    });
  }

  return normalizeCreatorFeedback(
    await requestJson(identity, `/checks/${encodeURIComponent(checkId)}/creator-feedback`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({
        fix_request_draft_id: input.fixRequestDraftId,
        message,
        ...(hasStart ? { start_ms: input.startMs, end_ms: input.endMs } : {}),
      }),
    }),
  );
}

export async function getComparison(
  identity: FixtureIdentity,
  currentCheckId: string,
  previousCheckId: string,
  signal?: AbortSignal,
): Promise<CheckComparison> {
  const query = new URLSearchParams({ previous_check_id: previousCheckId });
  const source = record(
    await requestJson(identity, `/checks/${currentCheckId}/comparison?${query}`, { signal }),
  );
  const groups: Array<[ComparisonItem["classification"], unknown[]]> = [
    ["added", arrayAt(source, "added")],
    ["persisted", arrayAt(source, "persisted", "still_detected")],
    ["resolved", arrayAt(source, "resolved", "no_longer_detected")],
    ["incomparable", arrayAt(source, "incomparable", "cannot_compare")],
  ];
  const explicit = arrayAt(source, "items", "findings");
  const items =
    explicit.length > 0
      ? explicit.map((item) => {
          const row = record(item);
          return {
            findingId: stringAt(row, ["finding_id", "id"]) || undefined,
            title: stringAt(row, ["title", "summary"], "Finding comparison"),
            classification: stringAt(row, ["classification", "status"], "incomparable") as ComparisonItem["classification"],
            reason: stringAt(row, ["reason"]) || undefined,
          };
        })
      : groups.flatMap(([classification, rows]) =>
          rows.map((item) => {
            const row = record(item);
            return {
              findingId: stringAt(row, ["finding_id", "id"]) || undefined,
              title: stringAt(row, ["title", "summary"], "Finding comparison"),
              classification,
              reason: stringAt(row, ["reason"]) || undefined,
            };
          }),
        );
  return {
    previousCheckId: stringAt(source, ["previous_check_id"], previousCheckId),
    currentCheckId: stringAt(source, ["current_check_id"], currentCheckId),
    items,
    coverageCompatible: booleanAt(source, ["coverage_compatible", "compatible_versions"], true),
    changedVersions: arrayAt(source, "changed_versions", "version_changes").map(String),
  };
}

interface UploadSubmissionInput {
  campaignId: string;
  submissionId?: string;
  file: File;
  caption: string;
  creatorId: string;
  rightsAttested: boolean;
  noticeVersion: string;
  noticeAcknowledged: true;
}

export async function uploadSubmission(
  identity: FixtureIdentity,
  input: UploadSubmissionInput,
): Promise<SubmissionVersion> {
  const contentType = input.file.type || "video/mp4";
  if (input.file.size === 0 || input.file.size > MAX_UPLOAD_BYTES) {
    throw new ApiError({ code: "UPLOAD_SIZE_INVALID", message: "Choose a non-empty video up to 5 MB. Export a smaller MP4 or WebM before uploading." });
  }
  if (contentType !== "video/mp4" && contentType !== "video/webm") {
    throw new ApiError({ code: "UNSUPPORTED_MEDIA_TYPE", message: "Select an MP4 or WebM video." });
  }
  const authorization = record(
    await requestJson(identity, "/uploads", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        campaign_id: input.campaignId,
        filename: input.file.name,
        content_type: contentType,
        byte_size: input.file.size,
        rights_attested: input.rightsAttested,
        notice_version: input.noticeVersion,
        notice_acknowledged: input.noticeAcknowledged,
        purpose: "campaign_check",
      } satisfies ApiSchemas["UploadIntentCreate"]),
    }),
  );
  const uploadId = stringAt(authorization, ["upload_id", "id"]);
  const contentUrl = stringAt(authorization, ["content_url", "upload_url"]);
  const uploadToken = stringAt(authorization, ["upload_token"]);
  if (!uploadId || !contentUrl || !uploadToken) {
    throw new ApiError({
      code: "INVALID_UPLOAD_AUTHORIZATION",
      message: "The API did not return complete upload instructions.",
    });
  }

  let uploadResponse: Response;
  try {
    uploadResponse = await fetch(apiUrl(contentUrl), {
      method: "PUT",
      headers: {
        ...buildIdentityHeaders(identity),
        "Content-Type": contentType,
        "X-Upload-Token": uploadToken,
      },
      body: input.file,
    });
  } catch (error) {
    throw new ApiError({
      code: "UPLOAD_INTERRUPTED",
      message: error instanceof Error ? `Upload interrupted. ${error.message}` : "Upload interrupted.",
      retryable: true,
    });
  }
  if (!uploadResponse.ok) {
    if (uploadResponse.status === 401) notifySessionExpired(identity.accessToken);
    throw new ApiError({
      status: uploadResponse.status,
      code: "UPLOAD_FAILED",
      message: "The authorized upload did not complete. Your caption has been preserved.",
      retryable: uploadResponse.status >= 500,
    });
  }

  const finalized = record(
    await requestJson(identity, `/uploads/${uploadId}/finalize`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        finalize_token: stringAt(authorization, ["finalize_token"]),
      } satisfies ApiSchemas["UploadFinalize"]),
    }),
  );
  const assetId = stringAt(finalized, ["asset_id", "media_asset_id", "resource_id", "id"]);
  const endpoint = input.submissionId
    ? `/submissions/${input.submissionId}/versions`
    : `/campaigns/${input.campaignId}/submissions`;
  const versionBody = {
    asset_id: assetId,
    caption: input.caption,
    rights_attested: input.rightsAttested,
  } satisfies ApiSchemas["SubmissionVersionCreate"];
  const submissionBody = input.submissionId ? versionBody : {
    ...versionBody,
    creator_id: input.creatorId,
  } satisfies ApiSchemas["SubmissionCreate"];
  const created = await requestJson(identity, endpoint, {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify(submissionBody),
  });
  const createdSource = record(created);
  const versions = arrayAt(createdSource, "versions", "submission_versions");
  const versionSource = valueAt(createdSource, "version", "submission_version") ?? versions.at(-1) ?? created;
  return normalizeVersion(versionSource, 0);
}

/** A deterministic MP4 fixture marker for exercising the authorized upload contract. */
export function createSyntheticMp4(): File {
  const bytes = new Uint8Array([
    0x00, 0x00, 0x00, 0x18, 0x66, 0x74, 0x79, 0x70, 0x69, 0x73, 0x6f, 0x6d,
    0x00, 0x00, 0x02, 0x00, 0x69, 0x73, 0x6f, 0x6d, 0x69, 0x73, 0x6f, 0x32,
    0x00, 0x00, 0x00, 0x08, 0x66, 0x72, 0x65, 0x65,
    0x00, 0x00, 0x00, 0x08, 0x6d, 0x64, 0x61, 0x74,
  ]);
  return new File([bytes], "authorized-synthetic-draft.mp4", {
    type: "video/mp4",
    lastModified: 1_792_531_200_000,
  });
}

function normalizeDeletionReceipt(value: unknown): DeletionReceipt {
  const source = record(value);
  return {
    id: stringAt(source, ["id", "deletion_request_id", "resource_id"]),
    resourceType: source.resource_type === "media_asset" ? "media_asset" : "submission",
    resourceId: stringAt(source, ["resource_id"]),
    status: stringAt(source, ["status", "deletion_status"], "requested"),
    notice: stringAt(source, ["notice"], "Check each destination before treating deletion as complete."),
    destinations: arrayAt(source, "destinations").map((item) => {
      const row = record(item);
      return { destination: stringAt(row, ["destination"]), status: stringAt(row, ["status"], "unknown") };
    }),
    requestedByKind: source.requested_by_kind === "retention" ? "retention" : "member",
    attemptCount: numberAt(source, ["attempt_count"]),
    maxAttempts: numberAt(source, ["max_attempts"], 3),
    createdAt: stringAt(source, ["created_at"]) || undefined,
    completedAt: stringAt(source, ["completed_at"]) || undefined,
    retryAfter: stringAt(source, ["retry_after"]) || undefined,
    lastErrorCode: stringAt(source, ["last_error_code"]) || undefined,
  };
}

export async function getDeletionRequests(
  identity: FixtureIdentity,
  campaignId: string,
  signal?: AbortSignal,
): Promise<DeletionReceipt[]> {
  const source = record(await requestJson(identity,
    `/deletion-requests?campaign_id=${encodeURIComponent(campaignId)}`, { signal }));
  if (!Array.isArray(source.items)) {
    throw new ApiError({ code: "INVALID_RESPONSE", message: "Deletion history could not be verified. Refresh to try again." });
  }
  return source.items.map(normalizeDeletionReceipt);
}

export async function requestDeletion(
  identity: FixtureIdentity,
  input: { submissionId: string } | { resourceType: DeletionReceipt["resourceType"]; resourceId: string },
): Promise<DeletionReceipt> {
  return normalizeDeletionReceipt(await requestJson(identity, "/deletion-requests", {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({
      resource_type: "submissionId" in input ? "submission" : input.resourceType,
      resource_id: "submissionId" in input ? input.submissionId : input.resourceId,
    } satisfies ApiSchemas["DeletionRequestCreate"]),
  }));
}

export async function withdrawProcessingAuthorization(identity: FixtureIdentity, receiptId: string): Promise<DeletionReceipt> {
  return normalizeDeletionReceipt(await requestJson(identity, `/consent-receipts/${encodeURIComponent(receiptId)}/withdraw`, {
    method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() },
  }));
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError || error instanceof Error
    ? error.message
    : "An unexpected error occurred.";
}
