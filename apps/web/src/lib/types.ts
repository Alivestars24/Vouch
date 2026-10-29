export type Role = "admin" | "marketer" | "reviewer" | "viewer";

export type InvocationMode = "fixture" | "recorded" | "live";
export type AnalysisStatus =
  | "queued"
  | "running"
  | "completed"
  | "partial"
  | "failed"
  | "cancelled";
export type MachineAssessment =
  | "no_issues_detected"
  | "fixes_suggested"
  | "potentially_blocking"
  | "human_review_required"
  | "not_assessed";
export type ReviewStatus =
  | "unreviewed"
  | "changes_requested"
  | "approved"
  | "rejected"
  | "superseded"
  | "revoked";

export interface FixtureIdentity {
  key: string;
  label: string;
  hint: string;
  user: string;
  organizationId: string;
  organizationLabel: string;
  /** Transport only; membership and roles are always verified by the API. */
  accessToken?: string;
}

export interface Workspace {
  id: string;
  name: string;
  roles: Role[];
  membershipStatus: string;
}

export interface Campaign {
  id: string;
  name: string;
  objective: string;
  market: string;
  brandName: string;
  productName?: string;
  productId?: string;
  creatorIds: string[];
  status: string;
  createdAt?: string;
  currentActions: string[];
  pinnedRulePack?: {
    id?: string;
    name: string;
    version: string;
    reviewStatus: string;
  };
}

export type TrackEventKind = "click" | "order" | "refund";
export type TrackEnvironment = "test" | "live";

export interface TrackEvent {
  id: string;
  creatorId: string;
  eventKind: TrackEventKind;
  environment: TrackEnvironment;
  externalEventId: string;
  orderExternalId?: string;
  amountMinor: number;
  currency: string;
  attributionStatus: "attributed" | "ambiguous" | "unattributed";
  attributionMethod: string;
  occurredAt: string;
  receivedAt: string;
}

export interface TrackEnvironmentSummary {
  clicks: number;
  orders: number;
  refunds: number;
  conversionRate?: number;
  totalsByCurrency: Record<string, {
    grossMinor: number;
    refundedMinor: number;
    netMinor: number;
  }>;
}

export interface CampaignTrack {
  campaignId: string;
  freshnessAt?: string;
  test: TrackEnvironmentSummary;
  live: TrackEnvironmentSummary;
  events: TrackEvent[];
}

export interface CampaignReadinessCitation {
  sourceType: "campaign" | "submission" | "submission_version" | "analysis" | "review_context" | "deletion_request";
  sourceId: string;
  label: string;
  href: string;
}

export interface CampaignReadinessItem {
  id: string;
  severity: "blocker" | "action" | "ready";
  category: "upload" | "check" | "evidence" | "review" | "cleanup";
  title: string;
  detail: string;
  actionLabel: string;
  citation: CampaignReadinessCitation;
}

export interface CampaignReadiness {
  campaignId: string;
  generationMode: "deterministic_records";
  ready: boolean;
  blockerCount: number;
  actionCount: number;
  summary: string;
  items: CampaignReadinessItem[];
  limitations: string[];
}

export interface CatalogProduct {
  id: string;
  name: string;
  sku: string;
}

export interface CatalogCreator {
  id: string;
  name: string;
  handle: string;
  rightsStatus: string;
}

export interface GuestInvitation {
  id: string;
  campaignId: string;
  creatorId: string;
  submissionId: string;
  allowedActions: Array<"read_submission" | "upload_source" | "submit_version">;
  expiresAt: string;
  invitationUrl: string;
}

export interface RulePackVersion {
  id: string;
  name: string;
  version: string;
  status: string;
}

export type CapabilityStatus =
  | "not_configured"
  | "awaiting_access"
  | "policy_restricted"
  | "configured_unverified"
  | "ready"
  | "degraded"
  | "disabled";

export interface Capability {
  id: string;
  family: "Spark" | "Voice Transcribe" | "SAM" | "Image" | "Wonder" | string;
  role: string;
  status: CapabilityStatus;
  reason: string;
  market?: string;
  invocationMode?: InvocationMode;
  policyVersion?: string;
}

export interface MediaProcessing {
  mode: "fixture" | "decoded";
  processorVersion?: string;
}

export interface MediaProcessingMetadata extends MediaProcessing {
  durationMs?: number;
  width?: number;
  height?: number;
  frameRate?: number;
  audioPresent?: boolean;
  normalizedSha256?: string;
  sourceTimeMapping?: {
    kind: "identity";
    sourceOriginMs: number;
    normalizedOriginMs: number;
    precisionMs?: number;
  };
}

export interface ProcessingNotice {
  version: string;
  purpose: "campaign_check";
  noticeHash: string;
  body: string;
  title: string;
  status: "draft_local_only";
  publishedAt: string;
}

export interface ConsentReceipt {
  id: string;
  purpose: "campaign_check";
  noticeVersion: string;
  noticeHash: string;
  acceptedAt: string;
  actorUserId?: string;
  revokedAt?: string;
  revocationActorKind?: string;
  revocationReason?: string;
}

export type AuthorizationStatus = "active" | "revoked" | "legacy_no_notice" | "unknown";

export interface SubmissionVersion {
  id: string;
  versionNo: number;
  caption: string;
  createdAt?: string;
  uploader?: string;
  mediaHash?: string;
  captionHash?: string;
  assetName?: string;
  sourceDurationMs?: number;
  mediaProcessing?: MediaProcessingMetadata;
  authorizationStatus: AuthorizationStatus;
  consentReceipt?: ConsentReceipt;
  latestCheckId?: string;
  superseded: boolean;
}

export interface Submission {
  id: string;
  campaignId: string;
  creatorName: string;
  creatorId: string;
  versions: SubmissionVersion[];
  currentVersionId?: string;
}

export interface CoverageItem {
  modality: string;
  status: "complete" | "partial" | "missing" | "unknown";
  detail: string;
}

export interface FindingDecision {
  action: "accepted" | "dismissed" | "incorrect" | "uncertain";
  rationale: string;
  actor?: string;
  decidedAt?: string;
}

export interface Finding {
  id: string;
  title: string;
  severity: "critical" | "major" | "minor";
  ruleId: string;
  ruleVersion: string;
  ruleLabel: string;
  modality: string;
  startMs?: number;
  endMs?: number;
  captionSpan?: { start: number; end: number };
  timingPrecision?: string;
  evidenceText: string;
  uncertainty: string;
  suggestedAction: string;
  sourceUrl?: string;
  decision?: FindingDecision;
}

export interface ApprovalRecord {
  id: string;
  versionNo?: number;
  reviewStatus: ReviewStatus;
  reviewer: string;
  decidedAt: string;
  rationale?: string;
  manifestHash?: string;
  submissionVersionId?: string;
}

export interface ApprovalReportEvidence {
  id: string;
  modality: string;
  startMs?: number;
  endMs?: number;
  precision: string;
  description: string;
  capturedAt: string;
}

export interface ApprovalReportFinding {
  id: string;
  ruleId: string;
  ruleVersion: string;
  severity: string;
  evidenceIds: string[];
  startMs?: number;
  endMs?: number;
  evidenceText: string;
  uncertainty: string;
  suggestedAction: string;
  decision: "dismissed" | "incorrect";
  decisionRationale: string;
  decisionActorUserId: string;
  decidedAt: string;
}

export interface ApprovalReport {
  reportVersion: "approval-report.v1";
  exportedAt: string;
  currentStatus: "approved";
  approvalId: string;
  analysisId: string;
  campaignId: string;
  campaignName: string;
  submissionVersionId: string;
  submissionVersionNo: number;
  rulePackVersionId: string;
  manifestHash: string;
  mediaHash: string;
  captionHash: string;
  reviewerUserId: string;
  reviewerDisplayName: string;
  approvedAt: string;
  approvalRationale: string;
  invocationMode: InvocationMode;
  analysisStatus: "completed";
  schemaVersion: string;
  promptVersion: string;
  modelVersions: Record<string, string>;
  requiredCoverage: string[];
  observedCoverage: string[];
  evidence: ApprovalReportEvidence[];
  findings: ApprovalReportFinding[];
  limitations: string[];
}

export interface Check {
  id: string;
  submissionVersionId: string;
  analysisStatus: AnalysisStatus;
  machineAssessment: MachineAssessment;
  reviewStatus: ReviewStatus;
  invocationMode: InvocationMode;
  manifestHash: string;
  reviewVersion: number;
  scenario?: string;
  createdAt?: string;
  completedAt?: string;
  rulePackName: string;
  rulePackVersion: string;
  promptVersion?: string;
  modelVersion?: string;
  requiredCoverage: string[];
  coverage: CoverageItem[];
  evidence: Array<{
    id: string;
    modality: string;
    startMs?: number;
    endMs?: number;
    precision: string;
    description: string;
    capturedAt?: string;
  }>;
  missingIntervals: Array<{
    modality: string;
    startMs?: number;
    endMs?: number;
    reason: string;
  }>;
  findings: Finding[];
  approvals: ApprovalRecord[];
  failure?: {
    code: string;
    message: string;
    retryable: boolean;
  };
}

export interface AcceptedOperation {
  operationId: string;
  resourceId: string;
  status: string;
  statusUrl: string;
  invocationMode: InvocationMode;
}

export interface Job {
  id: string;
  status:
    | "queued"
    | "running"
    | "retry_wait"
    | "succeeded"
    | "failed"
    | "outcome_unknown"
    | "cancelled"
    | "dead_letter";
  stage?: string;
  attemptCount: number;
  retryAt?: string;
  resourceId?: string;
  resultId?: string;
  message?: string;
  retryable?: boolean;
}

export interface ComparisonItem {
  findingId?: string;
  title: string;
  classification: "added" | "persisted" | "resolved" | "incomparable";
  reason?: string;
}

export interface CheckComparison {
  previousCheckId: string;
  currentCheckId: string;
  items: ComparisonItem[];
  coverageCompatible: boolean;
  changedVersions: string[];
}

export interface FixRequestDraft {
  id?: string;
  message: string;
  createdAt?: string;
  sent: false;
}

export interface CreatorFeedback {
  id: string;
  submissionId: string;
  submissionVersionId: string;
  analysisId: string;
  fixRequestDraftId: string;
  versionNo: number;
  message: string;
  startMs?: number;
  endMs?: number;
  invocationMode: InvocationMode;
  analysisStatus: AnalysisStatus;
  manifestHash: string;
  historical: boolean;
  publishedAt: string;
}

export interface DeletionReceipt {
  id: string;
  resourceType: "media_asset" | "submission";
  resourceId: string;
  status: string;
  notice: string;
  destinations: Array<{ destination: string; status: string }>;
  requestedByKind: "member" | "retention";
  attemptCount: number;
  maxAttempts: number;
  createdAt?: string;
  completedAt?: string;
  retryAfter?: string;
  lastErrorCode?: string;
}
