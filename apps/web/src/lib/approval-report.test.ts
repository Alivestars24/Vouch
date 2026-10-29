import { describe, expect, it } from "vitest";

import { formatApprovalReport } from "@/lib/approval-report";
import type { ApprovalReport } from "@/lib/types";

const report: ApprovalReport = {
  reportVersion: "approval-report.v1",
  exportedAt: "2026-10-29T14:00:00Z",
  currentStatus: "approved",
  approvalId: "approval-1",
  analysisId: "analysis-1",
  campaignId: "campaign-1",
  campaignName: "Glow Serum Launch",
  submissionVersionId: "version-1",
  submissionVersionNo: 3,
  rulePackVersionId: "rule-pack-1",
  manifestHash: "a".repeat(64),
  mediaHash: "b".repeat(64),
  captionHash: "c".repeat(64),
  reviewerUserId: "reviewer-1",
  reviewerDisplayName: "Rohan Reviewer",
  approvedAt: "2026-10-29T13:55:00Z",
  approvalRationale: "Reviewed the cited evidence.\nExact version approved.",
  invocationMode: "fixture",
  analysisStatus: "completed",
  schemaVersion: "check-result.v1",
  promptVersion: "check-fixture-prompt.v1",
  modelVersions: { reasoner: "fixture-spark-v1" },
  requiredCoverage: ["speech", "visual"],
  observedCoverage: ["speech", "visual"],
  evidence: [{
    id: "evidence-1",
    modality: "speech",
    startMs: 0,
    endMs: 4000,
    precision: "fixture-exact",
    description: "Disclosure detected.",
    capturedAt: "2026-10-29T13:50:00Z",
  }],
  findings: [{
    id: "finding-1",
    ruleId: "disclosure.present",
    ruleVersion: "1.0",
    severity: "required",
    evidenceIds: ["evidence-1"],
    startMs: 0,
    endMs: 4000,
    evidenceText: "Sponsored disclosure is present.",
    uncertainty: "none",
    suggestedAction: "Keep the disclosure visible.",
    decision: "dismissed",
    decisionRationale: "Evidence satisfies the campaign rule.",
    decisionActorUserId: "reviewer-1",
    decidedAt: "2026-10-29T13:54:00Z",
  }],
  limitations: ["Fixture execution validates workflow behavior only."],
};

describe("approval report formatter", () => {
  it("renders exact version anchors, evidence, decisions, and the non-certificate warning", () => {
    const markdown = formatApprovalReport(report);

    expect(markdown).toContain("Vouch approval report · Glow Serum Launch");
    expect(markdown).toContain("not a legal compliance certificate");
    expect(markdown).toContain("Approved version: **v3**");
    expect(markdown).toContain(`Manifest SHA-256: \`${"a".repeat(64)}\``);
    expect(markdown).toContain("Disclosure detected.");
    expect(markdown).toContain("Decision: **dismissed**");
    expect(markdown).toContain("Reviewed the cited evidence. Exact version approved.");
  });
});
