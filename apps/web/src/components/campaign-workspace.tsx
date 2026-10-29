"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { SubmissionUploader } from "@/components/submission-uploader";
import { SignalActivity } from "@/components/signal-motion";
import { DeletionHistory } from "@/components/deletion-history";
import { MediaAssetMetadata } from "@/components/media-processing";
import { ProcessingAuthorization } from "@/components/processing-authorization";
import { CreatorInvitation } from "@/components/creator-invitation";
import { InlineNotice, StatePanel, StatusBadge, StatusTriptych } from "@/components/status";
import { useIdentity } from "@/components/identity-context";
import {
  decideFinding,
  errorMessage,
  getCampaign,
  getApprovalReport,
  getCatalog,
  getCheck,
  getComparison,
  getJob,
  getMediaProcessing,
  getSubmissions,
  makeReviewDecision,
  prepareFixRequest,
  publishCreatorFeedback,
  requestDeletion,
  startCheck,
} from "@/lib/api";
import { saveApprovalReport } from "@/lib/approval-report";
import { formatDateTime, formatTimecode, humanize } from "@/lib/format";
import type {
  Campaign,
  CatalogCreator,
  Check,
  CheckComparison,
  CreatorFeedback,
  DeletionReceipt,
  FindingDecision,
  FixRequestDraft,
  Job,
  MediaProcessing,
  Submission,
  SubmissionVersion,
} from "@/lib/types";

const SCENARIOS = [
  ["success", "Findings with complete evidence"],
  ["clean", "No findings with complete evidence"],
  ["partial_voice", "Incomplete voice evidence"],
  ["transient_then_success", "Retry once, then succeed"],
  ["invalid_output", "Reject invalid provider output"],
  ["provider_down", "Exhaust bounded retries"],
] as const;

function latestVersion(submission?: Submission): SubmissionVersion | undefined {
  return submission?.versions.find((version) => version.id === submission.currentVersionId)
    ?? submission?.versions[0];
}

interface CreatorFeedbackPublisherProps {
  canPublish: boolean;
  draft?: FixRequestDraft;
  invocationMode?: Check["invocationMode"];
  isPublishing: boolean;
  onPublish: (message: string) => Promise<void>;
  published?: CreatorFeedback;
}

export function CreatorFeedbackPublisher({
  canPublish,
  draft,
  invocationMode,
  isPublishing,
  onPublish,
  published,
}: CreatorFeedbackPublisherProps) {
  if (!draft) {
    return (
      <InlineNotice tone="neutral" title="Feedback is still private">
        <p>Prepare a revision note before sharing anything with the creator.</p>
      </InlineNotice>
    );
  }

  if (published) {
    return (
      <InlineNotice tone={published.historical ? "warning" : "success"} title="Shared to creator portal">
        <p>
          {published.historical ? "Historical feedback" : "Current feedback"} for version {published.versionNo}. {published.invocationMode === "fixture" ? "Fixture-derived" : humanize(published.invocationMode)} evidence / {humanize(published.analysisStatus)} analysis.
        </p>
        <p>Check manifest <code title={published.manifestHash}>{published.manifestHash.slice(0, 12)}...</code></p>
        <p>No external message was sent and no campaign content was published.</p>
      </InlineNotice>
    );
  }

  const missingDraftId = !draft.id;
  return (
    <div className="fix-draft">
      <label className="field full" htmlFor="creator-feedback-message">
        <span>Creator-visible message</span>
        <textarea
          id="creator-feedback-message"
          value={draft.message}
          readOnly
          rows={5}
        />
      </label>
      <p>
        {invocationMode === "fixture"
          ? "Fixture-derived note: the underlying evidence is deterministic test data."
          : invocationMode
            ? `${humanize(invocationMode)} provider provenance will remain attached to this snapshot.`
            : "Provider provenance has not been verified."}
      </p>
      <p>Sharing makes only this reviewed snapshot visible in the scoped creator portal. It does not send a message or publish campaign content externally.</p>
      {!canPublish ? <p>Admin, marketer or reviewer authority is required to share creator-visible feedback.</p> : null}
      {missingDraftId ? <p>This draft is missing its server reference. Prepare it again before sharing.</p> : null}
      <button
        className="button primary"
        type="button"
        disabled={!canPublish || missingDraftId || !draft.message.trim() || isPublishing}
        onClick={() => void onPublish(draft.message.trim())}
      >
        {isPublishing ? "Sharing..." : "Share in creator portal"}
      </button>
    </div>
  );
}

export function CampaignWorkspace({ campaignId }: { campaignId: string }) {
  const { identity, workspace } = useIdentity();
  const [campaign, setCampaign] = useState<Campaign>();
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [creators, setCreators] = useState<CatalogCreator[]>([]);
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<string>();
  const [check, setCheck] = useState<Check>();
  const [job, setJob] = useState<Job>();
  const [comparison, setComparison] = useState<CheckComparison>();
  const [fixDraft, setFixDraft] = useState<FixRequestDraft>();
  const [publishedFeedback, setPublishedFeedback] = useState<CreatorFeedback>();
  const [feedbackCommandId, setFeedbackCommandId] = useState<string>();
  const [feedbackCheckId, setFeedbackCheckId] = useState<string>();
  const [scenario, setScenario] = useState("success");
  const [busy, setBusy] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [statusUrl, setStatusUrl] = useState<string>();
  const [activeCheckId, setActiveCheckId] = useState<string>();
  const [deletion, setDeletion] = useState<DeletionReceipt>();
  const [mediaProcessing, setMediaProcessing] = useState<MediaProcessing>();
  const [mediaProcessingLoading, setMediaProcessingLoading] = useState(true);

  const updateDeletionReceipt = useCallback((receipt: DeletionReceipt) => {
    setDeletion((current) => current?.id === receipt.id ? receipt : current);
  }, []);
  const syncDeletionHistory = useCallback((receipts: DeletionReceipt[]) => {
    setDeletion((current) => {
      return receipts.find((item) => item.id === current?.id) ?? current;
    });
  }, []);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(undefined);
    try {
      const [campaignRow, submissionRows, catalog] = await Promise.all([
        getCampaign(identity, campaignId, signal),
        getSubmissions(identity, campaignId, signal),
        getCatalog(identity, signal),
      ]);
      setCampaign(campaignRow);
      setSubmissions(submissionRows);
      setCreators(catalog.creators);
      setSelectedSubmissionId((current) => current ?? submissionRows[0]?.id);
      const newestCheck = latestVersion(submissionRows[0])?.latestCheckId;
      if (newestCheck) setActiveCheckId((current) => current ?? newestCheck);
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(errorMessage(caught));
      }
    } finally {
      setLoading(false);
    }
  }, [campaignId, identity]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => void load(controller.signal));
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      setMediaProcessingLoading(true);
      void getMediaProcessing(identity, controller.signal)
        .then((processing) => { if (!controller.signal.aborted) setMediaProcessing(processing); })
        .catch(() => { if (!controller.signal.aborted) setMediaProcessing(undefined); })
        .finally(() => { if (!controller.signal.aborted) setMediaProcessingLoading(false); });
    });
    return () => controller.abort();
  }, [identity]);

  useEffect(() => {
    if (!activeCheckId) {
      return;
    }
    const controller = new AbortController();
    void getCheck(identity, activeCheckId, controller.signal)
      .then(setCheck)
      .catch((caught) => {
        if (!controller.signal.aborted) setError(errorMessage(caught));
      });
    return () => controller.abort();
  }, [activeCheckId, identity]);

  useEffect(() => {
    if (!statusUrl || ["succeeded", "failed", "outcome_unknown", "dead_letter", "cancelled"].includes(job?.status ?? "")) {
      return;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const next = await getJob(identity, statusUrl);
        if (cancelled) return;
        setJob(next);
        if (next.status === "succeeded") {
          const completedCheckId = next.resultId ?? next.resourceId;
          if (completedCheckId) {
            setActiveCheckId(completedCheckId);
            setCheck(await getCheck(identity, completedCheckId));
          }
          setStatusUrl(undefined);
          await load();
        } else if (["failed", "outcome_unknown", "dead_letter", "cancelled"].includes(next.status)) {
          setStatusUrl(undefined);
        }
      } catch (caught) {
        if (!cancelled) setError(errorMessage(caught));
      }
    };
    void poll();
    const interval = window.setInterval(() => void poll(), 700);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [identity, job?.status, load, statusUrl]);

  const selectedSubmission = submissions.find((item) => item.id === selectedSubmissionId)
    ?? submissions[0];
  const version = latestVersion(selectedSubmission);
  const checkedVersion = selectedSubmission?.versions.find((item) => item.id === check?.submissionVersionId);
  const scopedFixDraft = check?.id === feedbackCheckId ? fixDraft : undefined;
  const scopedPublishedFeedback = check?.id === feedbackCheckId ? publishedFeedback : undefined;
  const creatorId = selectedSubmission?.creatorId || campaign?.creatorIds[0] || "";
  const creatorName = creators.find((creator) => creator.id === creatorId)?.name
    ?? selectedSubmission?.creatorName
    ?? "Authorized creator";
  const canUpload = Boolean(workspace?.roles.some((role) => role === "admin" || role === "marketer"));
  const canReview = Boolean(workspace?.roles.includes("reviewer"));
  const canShareFeedback = Boolean(workspace?.roles.some((role) => role === "admin" || role === "marketer" || role === "reviewer"));
  const checkIds = useMemo(
    () => selectedSubmission?.versions.flatMap((item) => item.latestCheckId ? [item.latestCheckId] : []) ?? [],
    [selectedSubmission],
  );

  async function runCheck() {
    if (!version || version.authorizationStatus !== "active") return;
    setBusy("check");
    setError(undefined);
    setCheck(undefined);
    setComparison(undefined);
    try {
      const operation = await startCheck(identity, version.id, { scenario });
      setJob({ id: operation.operationId, status: "queued", attemptCount: 0, resourceId: operation.resourceId });
      setStatusUrl(operation.statusUrl);
      setActiveCheckId(operation.resourceId);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function recordDecision(findingId: string, action: FindingDecision["action"]) {
    if (!check) return;
    setBusy(`finding-${findingId}`);
    setError(undefined);
    try {
      await decideFinding(identity, findingId, {
        action,
        rationale: `Fixture reviewer marked this finding ${humanize(action)} after reviewing the cited evidence.`,
        expectedReviewVersion: check.reviewVersion,
      });
      setCheck(await getCheck(identity, check.id));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function review(action: "approve" | "request_changes" | "reject" | "revoke") {
    if (!check) return;
    setBusy(action);
    setError(undefined);
    try {
      setCheck(await makeReviewDecision(identity, check, {
        action,
        rationale: action === "approve"
          ? "Human reviewer approved this exact immutable fixture version."
          : "Human reviewer requested a revision based on the recorded evidence.",
      }));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function downloadApprovalReport() {
    if (!check) return;
    setBusy("approval-report");
    setError(undefined);
    try {
      saveApprovalReport(await getApprovalReport(identity, check.id));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function draftFixRequest() {
    if (!check) return;
    setBusy("fix-draft");
    setError(undefined);
    try {
      const draft = await prepareFixRequest(identity, check.id, check.findings.map((item) => item.id));
      setFixDraft(draft);
      setPublishedFeedback(undefined);
      setFeedbackCommandId(crypto.randomUUID());
      setFeedbackCheckId(check.id);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function shareCreatorFeedback(message: string) {
    if (!check || feedbackCheckId !== check.id || !scopedFixDraft?.id || !canShareFeedback) return;
    const commandId = feedbackCommandId ?? crypto.randomUUID();
    setFeedbackCommandId(commandId);
    setBusy("creator-feedback");
    setError(undefined);
    try {
      setPublishedFeedback(await publishCreatorFeedback(identity, check.id, {
        fixRequestDraftId: scopedFixDraft.id,
        message,
      }, commandId));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function compareWithPrevious() {
    if (!check || checkIds.length < 2) return;
    const previous = checkIds.find((id) => id !== check.id);
    if (!previous) return;
    setBusy("compare");
    try {
      setComparison(await getComparison(identity, check.id, previous));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function deleteSubmission(submissionId = selectedSubmission?.id) {
    if (!submissionId) return;
    setBusy("delete");
    try {
      const receipt = await requestDeletion(identity, { submissionId });
      setDeletion(receipt);
      setSelectedSubmissionId(undefined);
      setCheck(undefined);
      setActiveCheckId(undefined);
      setStatusUrl(undefined);
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function retryDeletion() {
    if (!deletion) return;
    setBusy("delete");
    try {
      setDeletion(await requestDeletion(identity, { resourceType: deletion.resourceType, resourceId: deletion.resourceId }));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function authorizationWithdrawn(receipt: DeletionReceipt) {
    setDeletion(receipt);
    setSelectedSubmissionId(undefined);
    setCheck(undefined);
    setActiveCheckId(undefined);
    setStatusUrl(undefined);
    await load();
  }

  if (loading && !campaign) {
    return <StatePanel kind="loading" title="Opening campaign"><p>Loading the organization-scoped review record...</p></StatePanel>;
  }
  if (!campaign) {
    return <StatePanel kind="error" title="Campaign unavailable"><p>{error ?? "The campaign was not found in this workspace."}</p></StatePanel>;
  }

  return (
    <div className="page-stack">
      <header className="page-header campaign-title">
        <div>
          <p className="eyebrow"><Link href="/">Workspace</Link> / Campaign</p>
          <h1>{campaign.name}</h1>
          <p className="lede">{campaign.objective}</p>
        </div>
        <div className="campaign-meta">
          <StatusBadge value="fixture" label="Fixture execution" />
          <span>Media: {mediaProcessing ? humanize(mediaProcessing.mode) : "Unverified"}</span>
          <span>{campaign.market} / {campaign.productName}</span>
          <span>{campaign.pinnedRulePack?.name} {campaign.pinnedRulePack?.version}</span>
        </div>
      </header>

      {error ? <InlineNotice tone="danger" title="Action did not complete"><p>{error}</p></InlineNotice> : null}

      <section className="workflow-strip" aria-label="Review workflow">
        {[
          ["1", "Upload", Boolean(version)],
          ["2", "Check", Boolean(check)],
          ["3", "Decide", Boolean(check?.findings.every((item) => item.decision))],
          ["4", "Revise", selectedSubmission?.versions.length ? selectedSubmission.versions.length > 1 : false],
          ["5", "Approve", check?.reviewStatus === "approved"],
        ].map(([number, label, done]) => (
          <div key={String(label)} className={done ? "done" : ""}><span>{number}</span><strong>{label}</strong></div>
        ))}
      </section>

      <div className="review-grid">
        <div className="primary-column page-stack">
          <SubmissionUploader
            campaignId={campaign.id}
            submission={selectedSubmission}
            creatorId={creatorId}
            creatorName={creatorName}
            canUpload={canUpload && Boolean(creatorId)}
            mediaProcessing={mediaProcessing}
            mediaProcessingLoading={mediaProcessingLoading}
            onUploaded={() => {
              setCheck(undefined);
              setActiveCheckId(undefined);
              setComparison(undefined);
              void load();
            }}
          />

          {version ? (
            <section className="check-launch" aria-labelledby="check-launch-heading">
              <div className="section-heading compact">
                <div><p className="eyebrow">Asynchronous Check</p><h2 id="check-launch-heading">Run deterministic evidence providers</h2></div>
                <span className="version-marker">v{version.versionNo}</span>
              </div>
              <label className="field full">
                <span>Fixture scenario</span>
                <select value={scenario} onChange={(event) => setScenario(event.target.value)} disabled={!canUpload || Boolean(statusUrl)}>
                  {SCENARIOS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <div className="form-footer">
                <p>Retries are bounded to three attempts. Reservations are released after terminal failure and settled at zero cost for fixtures.</p>
                <button className="button primary" onClick={() => void runCheck()} disabled={!canUpload || version.authorizationStatus !== "active" || busy === "check" || Boolean(statusUrl)}>
                  {statusUrl ? "Check running..." : "Start Check"}
                </button>
              </div>
              {job ? (
                <div className="job-line" aria-live="polite">
                  <SignalActivity status={job.status} />
                  <StatusBadge value={job.status} />
                  <span>Attempt {job.attemptCount || 1} / 3</span>
                  {job.message ? <span>{job.message}</span> : null}
                </div>
              ) : null}
            </section>
          ) : null}

          {check ? (
            <>
              <StatusTriptych check={check} />
              <section className="evidence-panel" aria-labelledby="evidence-heading">
                <div className="section-heading compact">
                  <div><p className="eyebrow">Timestamped evidence</p><h2 id="evidence-heading">Observed coverage</h2></div>
                  <code title={check.manifestHash}>{check.manifestHash.slice(0, 12)}...</code>
                </div>
                {check.invocationMode === "fixture" ? <InlineNotice tone="neutral" title="Synthetic fixture evidence"><p>These timestamps and descriptions are deterministic test data, not observations extracted from this video. Media decoding does not change provider provenance.</p></InlineNotice> : null}
                <div className="coverage-grid">
                  {check.coverage.map((item) => <div key={item.modality}><StatusBadge value={item.status} /><strong>{humanize(item.modality)}</strong><p>{item.detail}</p></div>)}
                </div>
                {check.missingIntervals.length ? (
                  <InlineNotice tone="warning" title="Evidence is incomplete">
                    {check.missingIntervals.map((gap, index) => <p key={`${gap.modality}-${index}`}>{humanize(gap.modality)}: {formatTimecode(gap.startMs)}-{formatTimecode(gap.endMs)} / {gap.reason}</p>)}
                  </InlineNotice>
                ) : null}
                <ol className="evidence-list">
                  {check.evidence.map((item) => (
                    <li key={item.id}><span className="mono">{formatTimecode(item.startMs)}-{formatTimecode(item.endMs)}</span><div><strong>{humanize(item.modality)} / {humanize(item.precision)}</strong><p>{item.description}</p>{item.capturedAt ? <small>Captured {formatDateTime(item.capturedAt)}</small> : null}</div></li>
                  ))}
                </ol>
              </section>

              <section className="findings-panel" aria-labelledby="findings-heading">
                <div className="section-heading compact">
                  <div><p className="eyebrow">Finding decisions</p><h2 id="findings-heading">{check.findings.length ? `${check.findings.length} items need judgment` : check.analysisStatus === "completed" ? "No findings in observed coverage" : "Findings are not complete"}</h2></div>
                  <StatusBadge value={check.machineAssessment} />
                </div>
                {check.findings.map((finding) => (
                  <article className="finding-card" key={finding.id}>
                    <div className="finding-title"><StatusBadge value={finding.severity} /><div><strong>{finding.ruleId} / {finding.ruleVersion}</strong><span>{formatTimecode(finding.startMs)}-{formatTimecode(finding.endMs)}</span></div></div>
                    <blockquote>{finding.evidenceText}</blockquote>
                    <p>{finding.suggestedAction}</p>
                    <small>Uncertainty: {finding.uncertainty}</small>
                    {finding.decision ? (
                      <InlineNotice tone="neutral" title={`Recorded: ${humanize(finding.decision.action)}`}><p>{finding.decision.rationale}</p></InlineNotice>
                    ) : (
                      <div className="decision-actions">
                        {(["dismissed", "incorrect", "accepted", "uncertain"] as const).map((action) => (
                          <button key={action} className="button secondary small" disabled={!canReview || Boolean(busy)} onClick={() => void recordDecision(finding.id, action)}>{humanize(action)}</button>
                        ))}
                      </div>
                    )}
                  </article>
                ))}
                {check.findings.length ? <button className="button secondary" onClick={() => void draftFixRequest()} disabled={!canShareFeedback || Boolean(busy)}>Prepare revision note</button> : null}
                {check.findings.length ? (
                  <CreatorFeedbackPublisher
                    key={`${check.id}:${scopedFixDraft?.id ?? "private"}`}
                    canPublish={canShareFeedback}
                    draft={scopedFixDraft}
                    invocationMode={check.invocationMode}
                    isPublishing={busy === "creator-feedback"}
                    onPublish={shareCreatorFeedback}
                    published={scopedPublishedFeedback}
                  />
                ) : null}
              </section>

              <section className="approval-panel" aria-labelledby="approval-heading">
                <div><p className="eyebrow">Human approval</p><h2 id="approval-heading">Bind a decision to this exact manifest</h2><p>Approval never certifies legal compliance or publishes the draft. Incomplete evidence and unresolved findings block it.</p></div>
                <div className="decision-actions">
                  <button className="button secondary" disabled={!canReview || Boolean(busy)} onClick={() => void review("request_changes")}>Request changes</button>
                  <button className="button primary" disabled={!canReview || checkedVersion?.authorizationStatus !== "active" || Boolean(busy) || check.reviewStatus === "approved"} onClick={() => void review("approve")}>Approve exact version</button>
                  {check.reviewStatus === "approved" ? <button className="button secondary" disabled={Boolean(busy)} onClick={() => void downloadApprovalReport()}>{busy === "approval-report" ? "Preparing report…" : "Download approval report"}</button> : null}
                </div>
                {check.approvals.map((approval) => <InlineNotice key={approval.id} tone="success" title="Human approval recorded"><p>Manifest {approval.manifestHash?.slice(0, 12)}... / {formatDateTime(approval.decidedAt)}</p></InlineNotice>)}
              </section>

              {checkIds.length > 1 ? (
                <section className="comparison-panel">
                  <button className="button secondary" disabled={Boolean(busy)} onClick={() => void compareWithPrevious()}>Compare with previous Check</button>
                  {comparison ? <ul>{comparison.items.map((item, index) => <li key={`${item.findingId}-${index}`}><StatusBadge value={item.classification} /><span>{item.title}</span></li>)}</ul> : null}
                </section>
              ) : null}
            </>
          ) : null}
        </div>

        <aside className="secondary-column campaign-sidebar">
          <CreatorInvitation
            identity={identity}
            campaignId={campaign.id}
            creatorId={creatorId}
            creatorName={creatorName}
            canInvite={canUpload && Boolean(creatorId)}
          />
          <section className="context-card">
            <p className="eyebrow">Version history</p>
            <h2>Immutable snapshots</h2>
            {submissions.length === 0 ? <p>No submission yet.</p> : submissions.map((submission) => (
              <div key={submission.id}>
                <button className="submission-select" onClick={() => setSelectedSubmissionId(submission.id)}>{creatorName}</button>
                <ol className="version-list">
                  {submission.versions.map((item) => <li key={item.id} className={item.id === version?.id ? "active" : ""}><div><strong>v{item.versionNo}</strong><span>{item.createdAt ? formatDateTime(item.createdAt) : "Fixture snapshot"}</span></div>{item.latestCheckId ? <button onClick={() => setActiveCheckId(item.latestCheckId)}>View Check</button> : <span>Not checked</span>}</li>)}
                </ol>
              </div>
            ))}
          </section>
          {version ? <ProcessingAuthorization key={version.id} version={version} canWithdraw={canUpload} onWithdrawn={authorizationWithdrawn} /> : null}
          {version ? <section className="context-card">
            <p className="eyebrow">Media validation</p>
            <h2>Asset processing snapshot</h2>
            <MediaAssetMetadata metadata={version.mediaProcessing} />
          </section> : null}
          <section className="context-card">
            <p className="eyebrow">Privacy control</p>
            <h2>Deletion scope</h2>
            <p>Requests freeze related work and erase source media plus declared derivatives. Private Storage cleanup can remain retry-pending; a partial receipt is not complete. Fixture providers create no Meta artifacts.</p>
            <button className="button danger" disabled={!canUpload || !selectedSubmission || Boolean(busy)} onClick={() => void deleteSubmission()}>Delete submission data</button>
            {deletion ? (
              <InlineNotice tone={deletion.status === "completed" ? "success" : "warning"} title={deletion.status === "completed" ? "Deletion complete" : "Deletion incomplete: cleanup pending"}>
                <p>{deletion.notice}</p>
                <ul>{deletion.destinations.map((item) => <li key={item.destination}>{humanize(item.destination)}: {humanize(item.status)}</li>)}</ul>
                {deletion.status !== "completed" ? <button className="button secondary" disabled={!canUpload || Boolean(busy)} onClick={() => void retryDeletion()}>Retry storage cleanup</button> : null}
              </InlineNotice>
            ) : null}
          </section>
          <DeletionHistory
            key={campaign.id}
            campaignId={campaign.id}
            canRetry={canUpload}
            refreshKey={deletion ? `${deletion.id}:${deletion.status}:${deletion.attemptCount}` : undefined}
            onReceiptChange={updateDeletionReceipt}
            onHistoryLoaded={syncDeletionHistory}
          />
          <InlineNotice tone="neutral" title="Live product access remains gated"><p>This screen cannot select live mode. Each provider role still requires product-level quality and eligibility verification, and Muse Image remains restricted for India.</p></InlineNotice>
        </aside>
      </div>
    </div>
  );
}
