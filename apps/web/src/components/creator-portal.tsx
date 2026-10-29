"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import styles from "@/components/creator-portal.module.css";
import { CreatorSubmissionForm } from "@/components/creator-submission-form";
import {
  exchangeGuestInvitation,
  getGuestSubmission,
  GuestPortalError,
  GUEST_LINK_ENDED_MESSAGE,
  GUEST_UNAVAILABLE_MESSAGE,
  withdrawGuestSource,
  type GuestSubmission,
} from "@/lib/guest-api";

type FragmentClaim =
  | { kind: "invite"; secret: string }
  | { kind: "resume" }
  | { kind: "invalid" };

let claimedFragment: FragmentClaim | undefined;

function scrubFragment(): void {
  window.history.replaceState(
    window.history.state,
    "",
    `${window.location.pathname}${window.location.search}`,
  );
}

function claimInvitationFragment(): FragmentClaim {
  if (typeof window === "undefined") return { kind: "resume" };
  if (window.location.hash) {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const values = params.getAll("invite");
    const hasOnlyInvite = [...params.keys()].every((key) => key === "invite");
    const secret = values[0] ?? "";
    claimedFragment = values.length === 1
      && hasOnlyInvite
      && secret.length >= 32
      && secret.length <= 500
      ? { kind: "invite", secret }
      : { kind: "invalid" };
    scrubFragment();
    return claimedFragment;
  }
  return claimedFragment ?? { kind: "resume" };
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatTimeRange(start: number | null, end: number | null): string | null {
  if (start === null && end === null) return null;
  const seconds = (value: number) => `${Math.floor(value / 60_000)}:${String(Math.floor(value / 1000) % 60).padStart(2, "0")}`;
  if (start !== null && end !== null) return `${seconds(start)}–${seconds(end)}`;
  return seconds(start ?? end ?? 0);
}

function reviewLabel(submission: GuestSubmission["submission"]): string {
  if (submission.review_state === "approved" && submission.approved_version_no !== null) {
    return `Approved version ${submission.approved_version_no}`;
  }
  if (submission.review_state === "changes_requested") return "Changes requested";
  return "Awaiting brand review";
}

export function CreatorPortal() {
  const claim = useRef<FragmentClaim | null>(null);
  claim.current ??= claimInvitationFragment();
  const request = useRef<Promise<GuestSubmission> | null>(null);
  const [submission, setSubmission] = useState<GuestSubmission>();
  const [failure, setFailure] = useState<"ended" | "unavailable">();
  const [withdrawConfirm, setWithdrawConfirm] = useState(false);
  const [withdrawBusy, setWithdrawBusy] = useState(false);
  const [withdrawError, setWithdrawError] = useState<string>();
  const [withdrawn, setWithdrawn] = useState<"partial" | "completed">();
  const endGuestSession = useCallback(() => setFailure("ended"), []);

  useLayoutEffect(() => {
    // Next's hydration may restore the initial URL after the render-time scrub.
    // Repeat it before passive effects so the secret is absent before exchange.
    if (window.location.hash) scrubFragment();
  }, []);

  const canSubmitDraft = Boolean(
    submission
    && submission.allowed_actions.includes("upload_source")
    && submission.allowed_actions.includes("submit_version"),
  );

  const withdrawCurrentSource = useCallback(async () => {
    const receiptId = submission?.submission.current_version?.consent_receipt_id;
    if (!receiptId || withdrawBusy) return;
    setWithdrawBusy(true);
    setWithdrawError(undefined);
    try {
      const receipt = await withdrawGuestSource(receiptId);
      setWithdrawn(receipt.status === "completed" ? "completed" : "partial");
      setSubmission(undefined);
    } catch (error) {
      if (error instanceof GuestPortalError && error.kind === "ended") setFailure("ended");
      else setWithdrawError(error instanceof Error ? error.message : GUEST_UNAVAILABLE_MESSAGE);
    } finally {
      setWithdrawBusy(false);
    }
  }, [submission, withdrawBusy]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    if (claim.current?.kind === "invalid") {
      queueMicrotask(() => active && setFailure("ended"));
      return () => { active = false; };
    }

    request.current ??= (async () => {
      if (claim.current?.kind === "invite") {
        const secret = claim.current.secret;
        claim.current = { kind: "resume" };
        try {
          await exchangeGuestInvitation(secret, controller.signal);
        } finally {
          claimedFragment = undefined;
        }
      }
      return getGuestSubmission(controller.signal);
    })();

    void request.current
      .then((value) => { if (active) setSubmission(value); })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) return;
        setFailure(error instanceof GuestPortalError ? error.kind : "unavailable");
      });

    return () => {
      active = false;
      // Do not abort the one-time exchange during React Strict Mode's development effect replay.
    };
  }, []);

  const content = withdrawn ? (
    <section className={styles.state} role="status">
      <h1>Processing authorization withdrawn</h1>
      <p>{withdrawn === "completed"
        ? "The source and retained review content were erased. This private link can no longer open that draft."
        : "Access to the source ended immediately. Durable private-storage cleanup is still being confirmed by the brand workspace."}</p>
    </section>
  ) : failure ? (
    <section className={styles.state} role="alert">
      <h1>{failure === "ended" ? "This link has ended" : "Portal unavailable"}</h1>
      <p>{failure === "ended" ? GUEST_LINK_ENDED_MESSAGE : GUEST_UNAVAILABLE_MESSAGE}</p>
    </section>
  ) : submission ? (
    <article className={styles.portal}>
      <header className={styles.introduction}>
        <div>
          <p>{submission.campaign.brand_name} · Creator review</p>
          <h1>{submission.campaign.name}</h1>
          <p>
            Hi {submission.creator.name}. This private view shows only the draft and feedback
            the brand team shared for this campaign.
          </p>
        </div>
        <div className={styles.reviewBadge} role="status">
          {reviewLabel(submission.submission)}
        </div>
      </header>

      <div className={styles.grid}>
        <section className={styles.panel} aria-labelledby="draft-heading">
          <h2 id="draft-heading">Current draft</h2>
          {submission.submission.current_version ? <>
            <p className={styles.caption}>{submission.submission.current_version.caption || "No caption provided."}</p>
            <dl className={styles.metadata}>
              <div><dt>Version</dt><dd>{submission.submission.current_version.version_no}</dd></div>
              <div><dt>Submitted</dt><dd>{formatDate(submission.submission.current_version.created_at)}</dd></div>
              <div><dt>Market</dt><dd>{submission.campaign.market}</dd></div>
              <div><dt>Creator</dt><dd>{submission.creator.handle}</dd></div>
            </dl>
            {submission.submission.current_version.consent_receipt_id ? (
              <div className={styles.withdrawal}>
                <h3>Processing authorization</h3>
                <p>Withdrawing immediately blocks this source and starts its deletion workflow. Historical identifiers may remain for audit integrity; pending storage cleanup is not shown as complete.</p>
                {withdrawConfirm ? <>
                  <p><strong>Withdraw authorization and delete this exact source?</strong></p>
                  <div className={styles.withdrawActions}>
                    <button className={styles.dangerButton} type="button" disabled={withdrawBusy} onClick={() => void withdrawCurrentSource()}>{withdrawBusy ? "Withdrawing…" : "Confirm withdrawal"}</button>
                    <button className={styles.secondaryButton} type="button" disabled={withdrawBusy} onClick={() => setWithdrawConfirm(false)}>Cancel</button>
                  </div>
                </> : <button className={styles.secondaryButton} type="button" onClick={() => setWithdrawConfirm(true)}>Withdraw authorization and delete</button>}
                {withdrawError ? <p className={styles.formError} role="alert">{withdrawError}</p> : null}
              </div>
            ) : null}
          </> : (
            <p className={styles.empty}>
              {canSubmitDraft
                ? "No draft has been submitted yet. Use the private intake below when you are ready."
                : "No draft has been submitted yet. This link does not currently allow an upload."}
            </p>
          )}
        </section>

        <section className={styles.panel} aria-labelledby="feedback-heading">
          <h2 id="feedback-heading">Shared feedback</h2>
          {submission.feedback.length ? (
            <ul className={styles.feedback}>
              {submission.feedback.map((item, index) => {
                const timeRange = formatTimeRange(item.start_ms, item.end_ms);
                return <li key={`${item.version_no}-${item.published_at}-${index}`}>
                  <p>{item.message}</p>
                  <small>
                    Version {item.version_no}{timeRange ? ` · ${timeRange}` : ""} · {item.historical ? "Historical feedback" : "Current-version feedback"} · {item.invocation_mode === "fixture" ? "Fixture-derived Check" : `${item.invocation_mode} Check`} · {item.analysis_status} analysis · Shared {formatDate(item.published_at)}
                  </small>
                </li>;
              })}
            </ul>
          ) : <p className={styles.empty}>The brand team has not shared feedback yet.</p>}
        </section>
      </div>

      {canSubmitDraft ? (
        <CreatorSubmissionForm
          currentVersion={submission.submission.current_version}
          onSubmitted={setSubmission}
          onEnded={endGuestSession}
        />
      ) : null}

      <p className={styles.sessionNote}>
        This limited session ends {formatDate(submission.session_expires_at)}. It does not grant access to the brand workspace.
      </p>
    </article>
  ) : (
    <section className={styles.state} aria-live="polite" aria-busy="true">
      <span className={styles.status}>Opening private link</span>
      <h1>Preparing your campaign view</h1>
      <p>Verifying this invitation and its limited access.</p>
    </section>
  );

  return (
    <div className={styles.screen}>
      <a className={styles.skipLink} href="#creator-content">Skip to campaign</a>
      <header className={styles.header}>
        <div className={styles.brand}><BrandMark />Vouch</div>
        <span className={styles.privateLabel}>Private creator link</span>
      </header>
      <main id="creator-content" tabIndex={-1} className={styles.main}>{content}</main>
    </div>
  );
}
