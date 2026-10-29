"use client";

import { useMemo, useState } from "react";

import { StatusBadge } from "@/components/status";
import type { CreatorEvidence, FindCreator } from "@/lib/api";
import { formatTimecode, humanize } from "@/lib/format";
import type { Campaign } from "@/lib/types";

function readableTimestamp(value?: string): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unavailable"
    : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function sourceLink(evidence: CreatorEvidence) {
  if (!evidence.sourceUri || !/^https?:\/\//i.test(evidence.sourceUri)) return evidence.sourceLabel;
  return <a href={evidence.sourceUri} target="_blank" rel="noreferrer">{evidence.sourceLabel}</a>;
}

function buildDraft(creator: FindCreator, campaign: Campaign, organizationName: string): string {
  const evidence = creator.evidence.find((item) => item.matchKind === "exact_product") ?? creator.evidence[0];
  const relevance = evidence?.category && evidence.category !== "Uncategorized"
    ? `your work in ${evidence.category}`
    : "your creator work";
  return `Hi ${creator.name.split(" ")[0]},\n\nWe’re preparing ${campaign.name} for ${campaign.brandName}. Based on the authorized material in our collection, ${relevance} may be relevant to this campaign. Would you be open to reviewing the brief and deciding whether it is a fit?\n\nThanks,\n${organizationName}`;
}

export function CreatorInspector({
  creator,
  campaigns,
  campaignId,
  organizationName,
  canMutate,
  busy,
  actionError,
  actionMessage,
  onCampaignChange,
  onAdd,
}: {
  creator: FindCreator;
  campaigns: Campaign[];
  campaignId: string;
  organizationName: string;
  canMutate: boolean;
  busy: boolean;
  actionError?: string;
  actionMessage?: string;
  onCampaignChange: (campaignId: string) => void;
  onAdd: (evidenceId: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const campaign = campaigns.find((item) => item.id === campaignId);
  const eligibleEvidence = useMemo(() => {
    const allowed = creator.evidence.filter(
      (item) => item.permissionStatus !== "permission_unknown"
        && item.verificationStatus !== "unavailable",
    );
    const exact = allowed.filter(
      (item) => item.matchKind === "exact_product" && item.productId === campaign?.productId,
    );
    const category = allowed.filter((item) => item.matchKind === "category_relevance");
    return [...exact, ...category];
  }, [campaign?.productId, creator.evidence]);
  const [evidenceId, setEvidenceId] = useState(eligibleEvidence[0]?.id ?? "");
  const assignedCampaigns = useMemo(
    () => campaigns.filter((item) => item.creatorIds.includes(creator.id)),
    [campaigns, creator.id],
  );
  const alreadyAssigned = Boolean(campaign?.creatorIds.includes(creator.id));

  const prepareDraft = () => {
    if (!campaign) return;
    setDraft(buildDraft(creator, campaign, organizationName));
    setCopyStatus("Draft prepared locally. No message was sent.");
  };

  const copyDraft = async () => {
    try {
      await navigator.clipboard.writeText(draft);
      setCopyStatus("Draft copied. No message was sent.");
    } catch {
      setCopyStatus("Copy was blocked. Select the draft text and copy it manually.");
    }
  };

  return (
    <aside className="creator-inspector" aria-labelledby="creator-inspector-heading">
      <header className="creator-inspector-header">
        <div>
          <p className="eyebrow">Selected creator</p>
          <h2 id="creator-inspector-heading">{creator.name}</h2>
          <p>{creator.handle || "Handle not recorded"}</p>
        </div>
        <StatusBadge value={creator.rightsStatus} label={`Rights: ${humanize(creator.rightsStatus)}`} />
      </header>

      <section className="find-inspector-section" aria-labelledby="proof-heading">
        <div className="section-heading compact">
          <div><p className="eyebrow">Authorized proof</p><h3 id="proof-heading">Evidence and provenance</h3></div>
          <span className="find-count">{creator.evidence.length}</span>
        </div>
        {creator.evidence.length ? (
          <ol className="creator-evidence-list">
            {creator.evidence.map((evidence) => (
              <li key={evidence.id}>
                <div className="creator-evidence-title">
                  <strong>{evidence.category}</strong>
                  <span className={`find-match ${evidence.matchKind}`}>
                    {evidence.matchKind === "exact_product" ? "Exact product" : evidence.matchKind === "category_relevance" ? "Category relevance" : "Unreviewed"}
                  </span>
                </div>
                <p>{evidence.description}</p>
                <dl>
                  <div><dt>Source</dt><dd>{sourceLink(evidence)}</dd></div>
                  <div><dt>Permission</dt><dd>{humanize(evidence.permissionStatus)}</dd></div>
                  <div><dt>Status</dt><dd>{humanize(evidence.verificationStatus)}</dd></div>
                  <div><dt>Method</dt><dd>{humanize(evidence.evidenceMode)}</dd></div>
                  <div><dt>Captured</dt><dd>{readableTimestamp(evidence.capturedAt ?? creator.evidenceTimestamp)}</dd></div>
                  <div><dt>Proof type</dt><dd>{humanize(evidence.proofKind)}</dd></div>
                  {evidence.startMs !== undefined ? (
                    <div><dt>Moment</dt><dd className="mono">{formatTimecode(evidence.startMs)}{evidence.endMs !== undefined ? `–${formatTimecode(evidence.endMs)}` : ""}</dd></div>
                  ) : null}
                </dl>
              </li>
            ))}
          </ol>
        ) : <p className="find-muted">No authorized proof is attached. This creator remains unreviewed.</p>}
      </section>

      <section className="find-inspector-section" aria-labelledby="roster-heading">
        <div className="section-heading compact"><div><p className="eyebrow">Campaign roster</p><h3 id="roster-heading">Add with explicit scope</h3></div></div>
        {campaigns.length ? <>
          <label className="field" htmlFor="find-campaign"><span>Campaign</span><select id="find-campaign" value={campaignId} onChange={(event) => onCampaignChange(event.target.value)}>{campaigns.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="field" htmlFor="find-evidence"><span>Evidence used for this roster decision</span><select id="find-evidence" value={evidenceId} onChange={(event) => setEvidenceId(event.target.value)} disabled={!eligibleEvidence.length}>{eligibleEvidence.length ? eligibleEvidence.map((item) => <option key={item.id} value={item.id}>{item.matchKind === "exact_product" ? "Exact product" : "Category relevance"} · {item.sourceLabel}</option>) : <option value="">No compatible evidence</option>}</select></label>
          <div className="find-actions"><button type="button" className="button primary" disabled={!canMutate || busy || !evidenceId} onClick={() => onAdd(evidenceId)}>{busy ? "Adding…" : alreadyAssigned ? "Verify evidence link" : "Add to campaign"}</button><span>{assignedCampaigns.length ? `On ${assignedCampaigns.length} loaded campaign${assignedCampaigns.length === 1 ? "" : "s"}.` : "Not on a loaded campaign roster."}</span></div>
          {!canMutate ? <p className="field-error" role="note">An admin or marketer role is required to change a roster.</p> : null}
        </> : <p className="find-muted">Create a campaign before adding a creator to a roster.</p>}
        {actionError ? <p className="field-error" role="alert">{actionError}</p> : null}
        {actionMessage ? <p className="find-action-success" role="status">{actionMessage}</p> : null}
      </section>

      <section className="find-inspector-section outreach-draft" aria-labelledby="outreach-heading">
        <div className="section-heading compact"><div><p className="eyebrow">Draft only</p><h3 id="outreach-heading">Review outreach</h3></div></div>
        <p className="find-muted">Preparing or copying a draft never sends a message. Vouch has no external messaging connection here.</p>
        <button type="button" className="button secondary" disabled={!campaign} onClick={prepareDraft}>Draft outreach</button>
        {draft ? <><label className="field" htmlFor="outreach-copy"><span>Editable message draft</span><textarea id="outreach-copy" rows={7} value={draft} onChange={(event) => setDraft(event.target.value)} /></label><button type="button" className="button secondary" onClick={() => void copyDraft()}>Copy draft</button></> : null}
        {copyStatus ? <p className="find-copy-status" role="status">{copyStatus}</p> : null}
      </section>
    </aside>
  );
}
