"use client";

import { useRef, useState } from "react";

import { createGuestInvitation, errorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { FixtureIdentity, GuestInvitation } from "@/lib/types";

export function CreatorInvitation({
  identity,
  campaignId,
  creatorId,
  creatorName,
  canInvite,
}: {
  identity: FixtureIdentity;
  campaignId: string;
  creatorId: string;
  creatorName: string;
  canInvite: boolean;
}) {
  const recoveryId = useRef<string | undefined>(undefined);
  const [invitation, setInvitation] = useState<GuestInvitation>();
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string>();

  async function createLink() {
    if (!canInvite || busy || invitation) return;
    recoveryId.current ??= crypto.randomUUID();
    setBusy(true);
    setError(undefined);
    try {
      setInvitation(await createGuestInvitation(identity, campaignId, {
        creatorId,
        recoveryId: recoveryId.current,
      }));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function copyLink() {
    if (!invitation) return;
    try {
      await navigator.clipboard.writeText(invitation.invitationUrl);
      setCopied(true);
      setError(undefined);
    } catch {
      setError("Copying was blocked by the browser. Select the link and copy it manually.");
    }
  }

  return (
    <section className="context-card" aria-labelledby="creator-invitation-heading">
      <p className="eyebrow">Creator submission</p>
      <h2 id="creator-invitation-heading">Private upload link</h2>
      <p>
        Create a single-use invitation for {creatorName}. Opening the link does not grant access
        to this workspace, and Vouch does not send it automatically.
      </p>
      {invitation ? (
        <div className="guest-invitation-result">
          <label className="field full">
            <span>Creator link</span>
            <input readOnly value={invitation.invitationUrl} onFocus={(event) => event.currentTarget.select()} />
          </label>
          <div className="form-footer">
            <small>Expires {formatDateTime(invitation.expiresAt)}</small>
            <button className="button secondary small" type="button" onClick={() => void copyLink()}>
              {copied ? "Copied" : "Copy link"}
            </button>
          </div>
        </div>
      ) : (
        <button
          className="button secondary"
          type="button"
          disabled={!canInvite || !creatorId || busy}
          onClick={() => void createLink()}
        >
          {busy ? "Creating link…" : "Create private upload link"}
        </button>
      )}
      {!canInvite ? <p className="field-error" role="note">An admin or marketer role is required.</p> : null}
      {error ? <p className="field-error" role="alert">{error}</p> : null}
      <p className="fine-print">Share through your approved channel. The invitation is not an outreach send action.</p>
    </section>
  );
}
