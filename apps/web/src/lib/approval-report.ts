import type { ApprovalReport } from "@/lib/types";

function safeInline(value: string): string {
  return value.replaceAll("\r", " ").replaceAll("\n", " ").trim();
}

function timeRange(startMs?: number, endMs?: number): string {
  if (startMs === undefined || endMs === undefined) return "Not time-bound";
  return `${startMs}–${endMs} ms`;
}

export function formatApprovalReport(report: ApprovalReport): string {
  const modelRows = Object.entries(report.modelVersions)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([role, version]) => `- ${safeInline(role)}: \`${safeInline(version)}\``);
  const evidenceRows = report.evidence.map(
    (item) => `- **${safeInline(item.modality)}** (${timeRange(item.startMs, item.endMs)}, ${safeInline(item.precision)}): ${safeInline(item.description)}`,
  );
  const findingRows = report.findings.map(
    (item) => [
      `### ${safeInline(item.ruleId)} · ${safeInline(item.severity)}`,
      "",
      `- Rule version: \`${safeInline(item.ruleVersion)}\``,
      `- Range: ${timeRange(item.startMs, item.endMs)}`,
      `- Decision: **${safeInline(item.decision)}**`,
      `- Decision rationale: ${safeInline(item.decisionRationale)}`,
      `- Evidence: ${safeInline(item.evidenceText)}`,
      `- Suggested action: ${safeInline(item.suggestedAction)}`,
    ].join("\n"),
  );

  return [
    `# Vouch approval report · ${safeInline(report.campaignName)}`,
    "",
    "> This is a record of a human decision for one immutable version. It is not a legal compliance certificate or a publication instruction.",
    "",
    "## Approval",
    "",
    `- Current status at export: **${report.currentStatus}**`,
    `- Approved version: **v${report.submissionVersionNo}** (\`${report.submissionVersionId}\`)`,
    `- Reviewer: ${safeInline(report.reviewerDisplayName)} (\`${report.reviewerUserId}\`)`,
    `- Approved at: ${report.approvedAt}`,
    `- Exported at: ${report.exportedAt}`,
    `- Rationale: ${safeInline(report.approvalRationale)}`,
    "",
    "## Immutable binding",
    "",
    `- Manifest SHA-256: \`${report.manifestHash}\``,
    `- Media SHA-256: \`${report.mediaHash}\``,
    `- Caption SHA-256: \`${report.captionHash}\``,
    `- Analysis: \`${report.analysisId}\``,
    `- Approval: \`${report.approvalId}\``,
    `- Rule pack version: \`${report.rulePackVersionId}\``,
    "",
    "## Check provenance",
    "",
    `- Invocation mode: **${report.invocationMode}**`,
    `- Analysis status: **${report.analysisStatus}**`,
    `- Result schema: \`${safeInline(report.schemaVersion)}\``,
    `- Prompt version: \`${safeInline(report.promptVersion)}\``,
    `- Required coverage: ${report.requiredCoverage.map(safeInline).join(", ") || "None recorded"}`,
    `- Observed coverage: ${report.observedCoverage.map(safeInline).join(", ") || "None recorded"}`,
    ...modelRows,
    "",
    "## Evidence reviewed",
    "",
    ...(evidenceRows.length ? evidenceRows : ["No evidence rows were recorded."]),
    "",
    "## Finding decisions",
    "",
    ...(findingRows.length ? findingRows : ["No findings were recorded in the observed coverage."]),
    "",
    "## Limitations",
    "",
    ...report.limitations.map((item) => `- ${safeInline(item)}`),
    "",
  ].join("\n");
}

export function saveApprovalReport(report: ApprovalReport): void {
  const blob = new Blob([formatApprovalReport(report)], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const campaignSlug = report.campaignName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "campaign";
  anchor.href = url;
  anchor.download = `vouch-${campaignSlug}-approval-v${report.submissionVersionNo}.md`;
  anchor.click();
  URL.revokeObjectURL(url);
}
