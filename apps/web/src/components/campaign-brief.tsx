"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import { InlineNotice, StatusBadge } from "@/components/status";
import {
  createCampaignRequirement,
  createProductClaim,
  errorMessage,
  getCampaignBrief,
} from "@/lib/api";
import { humanize } from "@/lib/format";
import type {
  CampaignBrief,
  CampaignRequirementKind,
  FixtureIdentity,
} from "@/lib/types";

interface CampaignBriefPanelProps {
  campaignId: string;
  productId: string;
  identity: FixtureIdentity;
  canManage: boolean;
  refreshKey?: string;
}

const REQUIREMENT_KINDS: Array<[CampaignRequirementKind, string]> = [
  ["disclosure", "Spoken disclosure"],
  ["product_visibility", "Product visibility"],
  ["cta", "Call to action"],
  ["exact_phrase", "Required brand phrase"],
  ["approved_claim", "Approved product claim"],
];

export function CampaignBriefPanel({
  campaignId,
  productId,
  identity,
  canManage,
  refreshKey,
}: CampaignBriefPanelProps) {
  const [brief, setBrief] = useState<CampaignBrief>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState<"claim" | "requirement">();
  const [kind, setKind] = useState<CampaignRequirementKind>("disclosure");
  const [label, setLabel] = useState("");
  const [expectedText, setExpectedText] = useState("");
  const [claimId, setClaimId] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      setBrief(await getCampaignBrief(identity, campaignId, signal));
      setError(undefined);
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(errorMessage(caught));
      }
    }
  }, [campaignId, identity]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => void load(controller.signal));
    return () => controller.abort();
  }, [load, refreshKey]);

  async function addClaim(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy("claim");
    setError(undefined);
    try {
      const expiry = String(data.get("expiresAt") ?? "");
      await createProductClaim(identity, productId, {
        approvedWording: String(data.get("approvedWording") ?? ""),
        evidenceLabel: String(data.get("evidenceLabel") ?? ""),
        evidenceUri: String(data.get("evidenceUri") ?? ""),
        expiresAt: expiry ? new Date(expiry).toISOString() : undefined,
      });
      event.currentTarget.reset();
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function addRequirement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("requirement");
    setError(undefined);
    try {
      await createCampaignRequirement(identity, campaignId, {
        kind,
        label,
        expectedText: ["cta", "exact_phrase"].includes(kind) ? expectedText : undefined,
        claimId: kind === "approved_claim" ? claimId : undefined,
      });
      setLabel("");
      setExpectedText("");
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(undefined);
    }
  }

  return (
    <section className="campaign-brief" id="campaign-brief" aria-labelledby="campaign-brief-heading">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Content specification</p>
          <h2 id="campaign-brief-heading">Brief coverage and approved claims</h2>
          <p>Observed, missing and unknown stay tied to the current caption and Check evidence.</p>
        </div>
        <StatusBadge value={brief?.requirements.length ? "configured" : "not_configured"} />
      </div>

      {error ? <InlineNotice tone="danger" title="Content specification unavailable"><p>{error}</p></InlineNotice> : null}

      {brief?.requirements.length ? (
        <ol className="brief-requirements">
          {brief.requirements.map((requirement) => {
            const assessments = brief.assessments.filter(
              (assessment) => assessment.requirementId === requirement.id,
            );
            return (
              <li key={requirement.id}>
                <div className="brief-requirement-heading">
                  <span className="readiness-category">{humanize(requirement.kind)}</span>
                  <h3>{requirement.label}</h3>
                </div>
                {assessments.map((assessment, index) => (
                  <div className="brief-assessment" key={assessment.submissionId ?? index}>
                    <StatusBadge value={assessment.status} />
                    <p>{assessment.detail}</p>
                    {assessment.evidenceIds.length ? <small>{assessment.evidenceIds.length} evidence source(s)</small> : null}
                  </div>
                ))}
              </li>
            );
          })}
        </ol>
      ) : (
        <InlineNotice tone="neutral" title="No brief requirements yet">
          <p>Add only requirements the campaign actually needs. Unknown evidence will never be shown as a pass.</p>
        </InlineNotice>
      )}

      {brief?.claims.length ? (
        <div className="claim-library" aria-label="Approved product claims">
          <h3>Claim-to-evidence library</h3>
          {brief.claims.map((claim) => (
            <article key={claim.id}>
              <StatusBadge value={claim.status} />
              <strong>{claim.approvedWording}</strong>
              <span>{claim.evidenceLabel}</span>
            </article>
          ))}
        </div>
      ) : null}

      {canManage ? (
        <div className="brief-authoring">
          <details>
            <summary>Add approved claim evidence</summary>
            <form className="brief-form" onSubmit={addClaim}>
              <label className="field full"><span>Approved wording</span><textarea name="approvedWording" required maxLength={2000} rows={3} /></label>
              <label className="field"><span>Evidence label</span><input name="evidenceLabel" required maxLength={160} /></label>
              <label className="field"><span>Evidence reference</span><input name="evidenceUri" required maxLength={500} placeholder="Private document reference or URL" /></label>
              <label className="field"><span>Evidence expiry</span><input name="expiresAt" type="datetime-local" /></label>
              <button className="button secondary" disabled={Boolean(busy)} type="submit">{busy === "claim" ? "Saving..." : "Save approved claim"}</button>
            </form>
          </details>
          <details>
            <summary>Add brief requirement</summary>
            <form className="brief-form" onSubmit={addRequirement}>
              <label className="field"><span>Requirement type</span><select value={kind} onChange={(event) => setKind(event.target.value as CampaignRequirementKind)}>{REQUIREMENT_KINDS.map(([value, text]) => <option value={value} key={value}>{text}</option>)}</select></label>
              <label className="field full"><span>Reviewer-facing requirement</span><input value={label} onChange={(event) => setLabel(event.target.value)} required maxLength={160} /></label>
              {["cta", "exact_phrase"].includes(kind) ? <label className="field full"><span>Expected wording</span><input value={expectedText} onChange={(event) => setExpectedText(event.target.value)} required maxLength={2000} /></label> : null}
              {kind === "approved_claim" ? <label className="field full"><span>Approved claim</span><select value={claimId} onChange={(event) => setClaimId(event.target.value)} required><option value="">Select current evidence</option>{brief?.claims.filter((claim) => claim.status === "approved").map((claim) => <option value={claim.id} key={claim.id}>{claim.approvedWording}</option>)}</select></label> : null}
              <button className="button secondary" disabled={Boolean(busy)} type="submit">{busy === "requirement" ? "Saving..." : "Add requirement"}</button>
            </form>
          </details>
        </div>
      ) : null}

      {brief ? <p className="readiness-limit">{brief.limitations.join(" ")}</p> : null}
    </section>
  );
}
