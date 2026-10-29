"use client";

import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from "react";

import styles from "@/components/creator-portal.module.css";
import {
  getGuestProcessingNotice,
  GuestActionError,
  GuestPortalError,
  MAX_GUEST_UPLOAD_BYTES,
  submitGuestDraft,
  type GuestProcessingNotice,
  type GuestSubmission,
} from "@/lib/guest-api";

type CommandKeys = {
  intentIdempotencyKey: string;
  versionIdempotencyKey: string;
};

function newCommandKeys(): CommandKeys {
  const randomUuid = () => {
    if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  };
  return {
    intentIdempotencyKey: randomUuid(),
    versionIdempotencyKey: randomUuid(),
  };
}

function fileError(file: File | undefined): string | undefined {
  if (!file) return undefined;
  if (file.type !== "video/mp4" && file.type !== "video/webm") {
    return "Select an MP4 or WebM video.";
  }
  if (file.size === 0 || file.size > MAX_GUEST_UPLOAD_BYTES) {
    return "Choose a non-empty video up to 5 MB. Export a smaller MP4 or WebM before uploading.";
  }
  return undefined;
}

export function CreatorSubmissionForm({
  onSubmitted,
  onEnded,
  currentVersion,
}: {
  onSubmitted: (submission: GuestSubmission) => void;
  onEnded: () => void;
  currentVersion: GuestSubmission["submission"]["current_version"];
}) {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const commandKeys = useRef<CommandKeys | undefined>(undefined);
  const [notice, setNotice] = useState<GuestProcessingNotice>();
  const [noticeLoading, setNoticeLoading] = useState(true);
  const [noticeError, setNoticeError] = useState<string>();
  const [noticeAcknowledged, setNoticeAcknowledged] = useState(false);
  const [file, setFile] = useState<File>();
  const [caption, setCaption] = useState("");
  const [rightsAttested, setRightsAttested] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const invalidFile = fileError(file);

  const resetCommandKeys = useCallback(() => {
    commandKeys.current = undefined;
  }, []);

  const loadNotice = useCallback(async (signal?: AbortSignal) => {
    setNoticeLoading(true);
    setNoticeError(undefined);
    try {
      const current = await getGuestProcessingNotice(signal);
      setNotice(current);
      return current;
    } catch (caught) {
      if (signal?.aborted) return undefined;
      if (caught instanceof GuestPortalError && caught.kind === "ended") {
        onEnded();
        return undefined;
      }
      setNotice(undefined);
      setNoticeError(
        caught instanceof Error
          ? caught.message
          : "The creator processing notice could not be loaded. Try again.",
      );
      return undefined;
    } finally {
      if (!signal?.aborted) setNoticeLoading(false);
    }
  }, [onEnded]);

  useEffect(() => {
    const controller = new AbortController();
    void getGuestProcessingNotice(controller.signal).then((current) => {
      if (controller.signal.aborted) return;
      setNotice(current);
      setNoticeLoading(false);
    }).catch((caught: unknown) => {
      if (controller.signal.aborted) return;
      if (caught instanceof GuestPortalError && caught.kind === "ended") {
        onEnded();
        return;
      }
      setNotice(undefined);
      setNoticeError(
        caught instanceof Error
          ? caught.message
          : "The creator processing notice could not be loaded. Try again.",
      );
      setNoticeLoading(false);
    });
    return () => controller.abort();
  }, [onEnded]);

  function changeFile(next: File | undefined) {
    setFile(next);
    setError(undefined);
    setSuccess(undefined);
    resetCommandKeys();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      saving
      || !file
      || invalidFile
      || !caption.trim()
      || !rightsAttested
      || !notice
      || !noticeAcknowledged
    ) return;

    commandKeys.current ??= newCommandKeys();
    setSaving(true);
    setError(undefined);
    setSuccess(undefined);
    try {
      const authoritative = await submitGuestDraft({
        file,
        caption,
        expectedCurrentVersionId: currentVersion?.id ?? null,
        expectedVersionNo: (currentVersion?.version_no ?? 0) + 1,
        rightsAttested: true,
        noticeVersion: notice.version,
        noticeAcknowledged: true,
        ...commandKeys.current,
      });
      const version = authoritative.submission.current_version;
      if (!version) throw new GuestPortalError("unavailable");

      setFile(undefined);
      setCaption("");
      setRightsAttested(false);
      setNoticeAcknowledged(false);
      commandKeys.current = undefined;
      if (inputRef.current) inputRef.current.value = "";
      setSuccess(`Draft submitted as version ${version.version_no}.`);
      onSubmitted(authoritative);
    } catch (caught) {
      if (caught instanceof GuestPortalError && caught.kind === "ended") {
        onEnded();
        return;
      }
      const message = caught instanceof Error
        ? caught.message
        : "The draft could not be submitted. Try again.";
      setError(message);
      if (caught instanceof GuestActionError && caught.code === "NOTICE_VERSION_STALE") {
        setNoticeAcknowledged(false);
        resetCommandKeys();
        await loadNotice();
      }
    } finally {
      setSaving(false);
    }
  }

  const available = Boolean(notice) && !noticeLoading && !noticeError;

  return (
    <section className={styles.submissionPanel} aria-labelledby={`${id}-heading`}>
      <div className={styles.formHeading}>
        <div>
          <p className={styles.eyebrow}>Private creator intake</p>
          <h2 id={`${id}-heading`}>{currentVersion ? "Submit a revision" : "Submit your first draft"}</h2>
        </div>
        <span className={styles.versionPill}>Version {(currentVersion?.version_no ?? 0) + 1}</span>
      </div>

      <p className={styles.formIntroduction}>
        Upload one rights-cleared video and the exact caption you want the brand team to review.
        {currentVersion ? " The prior version and its feedback remain in the audit history." : ""}
      </p>

      <form className={styles.submissionForm} onSubmit={submit} noValidate>
        <div className={styles.field}>
          <label htmlFor={`${id}-file`}>MP4 or WebM video</label>
          <input
            ref={inputRef}
            id={`${id}-file`}
            type="file"
            accept="video/mp4,.mp4,video/webm,.webm"
            aria-describedby={`${id}-file-help`}
            aria-invalid={Boolean(invalidFile) || undefined}
            disabled={!available || saving}
            required
            onChange={(event) => changeFile(event.target.files?.[0])}
          />
          <small id={`${id}-file-help`}>
            {file
              ? `${file.name} · ${file.size.toLocaleString()} bytes · ${file.type || "type unavailable"}`
              : "Choose a non-empty MP4 or WebM up to 5 MB."}
          </small>
          {invalidFile ? <p className={styles.fieldError} role="alert">{invalidFile}</p> : null}
        </div>

        <div className={styles.field}>
          <label htmlFor={`${id}-caption`}>Caption snapshot</label>
          <textarea
            id={`${id}-caption`}
            value={caption}
            rows={4}
            maxLength={10_000}
            required
            disabled={!available || saving}
            placeholder="The exact caption proposed for this draft…"
            onChange={(event) => {
              setCaption(event.target.value);
              setError(undefined);
              setSuccess(undefined);
              resetCommandKeys();
            }}
          />
          <small>This caption is stored with the immutable version submitted for review.</small>
        </div>

        <label className={styles.checkRow}>
          <input
            type="checkbox"
            checked={rightsAttested}
            required
            disabled={!available || saving}
            onChange={(event) => {
              setRightsAttested(event.target.checked);
              setError(undefined);
              resetCommandKeys();
            }}
          />
          <span>I have the rights and permission needed to upload this video and caption for campaign review.</span>
        </label>

        <section className={styles.noticeCard} aria-labelledby={`${id}-notice-heading`}>
          {noticeLoading ? (
            <p role="status">Loading creator processing notice…</p>
          ) : notice ? (
            <>
              <h3 id={`${id}-notice-heading`}>{notice.title}</h3>
              <p className={styles.noticeBody}>{notice.body}</p>
              <label className={styles.checkRow}>
                <input
                  type="checkbox"
                  checked={noticeAcknowledged}
                  required
                  disabled={saving}
                  onChange={(event) => {
                    setNoticeAcknowledged(event.target.checked);
                    setError(undefined);
                    resetCommandKeys();
                  }}
                />
                <span>I acknowledge creator processing notice {notice.version} for this upload.</span>
              </label>
            </>
          ) : (
            <>
              <h3 id={`${id}-notice-heading`}>Creator processing notice unavailable</h3>
              <p>{noticeError ?? "The notice could not be loaded."}</p>
              <button
                className={styles.secondaryButton}
                type="button"
                disabled={noticeLoading || saving}
                onClick={() => {
                  setNoticeAcknowledged(false);
                  resetCommandKeys();
                  void loadNotice();
                }}
              >
                Retry notice loading
              </button>
            </>
          )}
        </section>

        {error ? <p className={styles.formError} role="alert">{error}</p> : null}
        {success ? <p className={styles.formSuccess} role="status">{success}</p> : null}

        <div className={styles.formFooter}>
          <p>{saving ? "Uploading and validating your draft…" : "The brand sees this draft only after validation finishes."}</p>
          <button
            className={styles.primaryButton}
            type="submit"
            disabled={
              saving
              || !available
              || !file
              || Boolean(invalidFile)
              || !caption.trim()
              || !rightsAttested
              || !noticeAcknowledged
            }
          >
            {saving ? "Submitting…" : "Submit draft"}
          </button>
        </div>
      </form>
    </section>
  );
}
