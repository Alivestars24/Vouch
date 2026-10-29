"use client";

import { useState } from "react";

import { useIdentity } from "@/components/identity-context";
import { InlineNotice, StatusBadge } from "@/components/status";
import { errorMessage, processingNoticeUrl, withdrawProcessingAuthorization } from "@/lib/api";
import { formatDateTime, humanize } from "@/lib/format";
import type { DeletionReceipt, SubmissionVersion } from "@/lib/types";

export function ProcessingAuthorization({ version, canWithdraw, onWithdrawn }: {
  version: SubmissionVersion;
  canWithdraw: boolean;
  onWithdrawn: (receipt: DeletionReceipt) => void | Promise<void>;
}) {
  const { identity } = useIdentity();
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [withdrawn, setWithdrawn] = useState(false);
  const [error, setError] = useState<string>();
  const receipt = version.consentReceipt;
  const status = withdrawn ? "revoked" : version.authorizationStatus;
  const active = status === "active" && Boolean(receipt);

  async function withdraw() {
    if (!receipt || !active || !canWithdraw || !confirmed || busy) return;
    setBusy(true);
    setError(undefined);
    try {
      const deletion = await withdrawProcessingAuthorization(identity, receipt.id);
      setWithdrawn(true);
      setConfirming(false);
      setConfirmed(false);
      await onWithdrawn(deletion);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="context-card" aria-label="Processing authorization">
      <p className="eyebrow">Workspace acknowledgment</p>
      <h2>Processing authorization</h2>
      <StatusBadge value={active ? "ready" : status} label={active ? "Authorization active" : humanize(status)} />
      <p>This is the workspace member’s processing acknowledgment, not proof of every depicted person’s legal consent.</p>
      {receipt ? <>
        <p>Purpose: campaign review ({receipt.purpose}).<br />Notice version: {receipt.noticeVersion}.<br />Accepted: {formatDateTime(receipt.acceptedAt)}.</p>
        {receipt.actorUserId ? <p>Acknowledging member: <code title={receipt.actorUserId}>{receipt.actorUserId.slice(0, 8)}</code></p> : null}
        <p>Notice hash: <code title={receipt.noticeHash}>{receipt.noticeHash.slice(0, 12)}…</code></p>
        <p><a href={processingNoticeUrl(receipt.noticeVersion)} target="_blank" rel="noreferrer">Read the accepted notice version (JSON)</a></p>
        {receipt.revokedAt ? <p>Revoked: {formatDateTime(receipt.revokedAt)}{receipt.revocationReason ? ` / ${humanize(receipt.revocationReason)}` : ""}.</p> : null}
        {receipt.revocationActorKind ? <p>Revocation actor: {humanize(receipt.revocationActorKind)}</p> : null}
      </> : null}
      {!active ? <p>{status === "legacy_no_notice"
        ? "This historical asset has no recorded notice acknowledgment. Upload a fresh acknowledged version for new processing or sign-off. Historical approvals are unchanged."
        : status === "revoked"
          ? "Authorization was revoked. A fresh acknowledged upload is required for new processing; cleanup outcomes remain in deletion history."
          : "Authorization provenance is unavailable. New processing and sign-off are blocked; upload a fresh acknowledged version."}</p> : null}
      {active && canWithdraw ? confirming ? <InlineNotice tone="warning" title="Confirm irreversible withdrawal">
        <p>Withdraw authorization for this exact source and delete its declared derivatives. Related work is stopped; physical cleanup may remain pending. This role-limited command is not universal privacy-rights fulfillment.</p>
        <label className="check-row"><input type="checkbox" checked={confirmed} disabled={busy} onChange={(event) => setConfirmed(event.target.checked)} /><span>I understand withdrawal cannot reactivate this source.</span></label>
        <button className="button danger" disabled={!confirmed || busy} onClick={() => void withdraw()}>{busy ? "Withdrawing..." : "Confirm withdrawal and delete"}</button>
        <button className="button secondary" disabled={busy} onClick={() => { setConfirming(false); setConfirmed(false); }}>Cancel withdrawal</button>
      </InlineNotice> : <button className="button danger" onClick={() => setConfirming(true)}>Withdraw authorization and delete</button> : null}
      {active && !canWithdraw ? <p>Only an admin or marketer can withdraw workspace processing authorization here.</p> : null}
      {error ? <InlineNotice tone="danger" title="Withdrawal did not complete"><p>{error}</p></InlineNotice> : null}
    </section>
  );
}
