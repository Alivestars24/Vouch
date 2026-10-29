"use client";

import { useId, useState, type FormEvent } from "react";

import { useIdentity } from "@/components/identity-context";
import { InlineNotice } from "@/components/status";
import { MediaModeNotice } from "@/components/media-processing";
import { ProcessingNoticeAcknowledgment } from "@/components/processing-notice";
import { useProcessingNotice } from "@/components/use-processing-notice";
import { ApiError, createSyntheticMp4, errorMessage, MAX_UPLOAD_BYTES, uploadSubmission } from "@/lib/api";
import type { MediaProcessing, Submission, SubmissionVersion } from "@/lib/types";

export function SubmissionUploader({
  campaignId,
  submission,
  creatorId,
  creatorName,
  canUpload,
  mediaProcessing,
  mediaProcessingLoading = false,
  onUploaded,
}: {
  campaignId: string;
  submission?: Submission;
  creatorId: string;
  creatorName: string;
  canUpload: boolean;
  mediaProcessing?: MediaProcessing;
  mediaProcessingLoading?: boolean;
  onUploaded: (version: SubmissionVersion) => void;
}) {
  const id = useId();
  const { identity } = useIdentity();
  const [file, setFile] = useState<File>();
  const [caption, setCaption] = useState("");
  const [rightsAttested, setRightsAttested] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const notice = useProcessingNotice();
  const invalidSize = Boolean(file && (file.size === 0 || file.size > MAX_UPLOAD_BYTES));
  const uploadAvailable = canUpload && Boolean(mediaProcessing) && !mediaProcessingLoading
    && Boolean(notice.notice) && !notice.loading;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || invalidSize || !rightsAttested || !notice.notice || !notice.acknowledged || !uploadAvailable || saving) return;
    setSaving(true);
    setError(undefined);
    try {
      const version = await uploadSubmission(identity, {
        campaignId,
        submissionId: submission?.id,
        file,
        caption,
        creatorId,
        rightsAttested,
        noticeVersion: notice.notice.version,
        noticeAcknowledged: true,
      });
      setFile(undefined);
      setCaption("");
      setRightsAttested(false);
      notice.setAcknowledged(false);
      const input = document.getElementById(`${id}-file`) as HTMLInputElement | null;
      if (input) input.value = "";
      onUploaded(version);
    } catch (caught) {
      setError(errorMessage(caught));
      if (caught instanceof ApiError && caught.code === "NOTICE_VERSION_STALE") {
        await notice.refresh();
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="upload-panel" aria-labelledby={`${id}-heading`}>
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">{submission ? "New immutable version" : "Authorized intake"}</p>
          <h2 id={`${id}-heading`}>{submission ? "Upload revision" : "Upload first draft"}</h2>
        </div>
        {submission ? <span className="version-marker">Next: v{(submission.versions[0]?.versionNo ?? 0) + 1}</span> : null}
      </div>

      <MediaModeNotice processing={mediaProcessing} loading={mediaProcessingLoading} />
      <form onSubmit={submit} className="upload-form">
        <div className="field full">
          <label htmlFor={`${id}-file`}>MP4 or WebM video</label>
          <div className="file-row">
            <input
              id={`${id}-file`}
              type="file"
              accept="video/mp4,.mp4,video/webm,.webm"
              aria-describedby={`${id}-file-help`}
              aria-invalid={invalidSize || undefined}
              onChange={(event) => setFile(event.target.files?.[0])}
              required={!file}
              disabled={!uploadAvailable || saving}
            />
            {mediaProcessing?.mode === "fixture" ? <button
              type="button"
              className="button secondary small"
              disabled={!uploadAvailable || saving}
              onClick={() => setFile(createSyntheticMp4())}
            >
              Use synthetic MP4
            </button> : null}
          </div>
          <small id={`${id}-file-help`}>
            {file
              ? `${file.name} · ${Math.max(file.size, 1).toLocaleString()} bytes · ${file.type || "type unknown"}`
              : mediaProcessing?.mode === "fixture" ? "Choose a rights-cleared MP4/WebM or the deterministic fixture marker." : "Choose a rights-cleared, decodable MP4 or WebM (up to 5 MB and 30 seconds)."}
          </small>
          {invalidSize ? <p className="field-error" role="alert">Choose a non-empty video up to 5 MB. Export a smaller MP4 or WebM before uploading; Vouch keeps that exact original for review.</p> : null}
        </div>

        <div className="field">
          <label htmlFor={`${id}-creator`}>Creator</label>
          <input
            id={`${id}-creator`}
            value={creatorName}
            required
            readOnly
            disabled={!uploadAvailable || saving}
          />
        </div>

        <div className="field full">
          <label htmlFor={`${id}-caption`}>Caption snapshot</label>
          <textarea
            id={`${id}-caption`}
            value={caption}
            onChange={(event) => setCaption(event.target.value)}
            rows={4}
            placeholder="The exact caption proposed for this version…"
            required
            disabled={!uploadAvailable || saving}
          />
          <small>Later edits create another version; they never overwrite this snapshot.</small>
        </div>

        <label className="check-row full">
          <input
            type="checkbox"
            checked={rightsAttested}
            onChange={(event) => setRightsAttested(event.target.checked)}
            required
            disabled={!uploadAvailable || saving}
          />
          <span>
            I confirm this organization is authorized to upload and analyze this video and caption
            for campaign review.
          </span>
        </label>

        <ProcessingNoticeAcknowledgment notice={notice.notice} loading={notice.loading} error={notice.error}
          acknowledged={notice.acknowledged} disabled={!uploadAvailable || saving}
          onAcknowledged={notice.setAcknowledged} onRetry={() => void notice.refresh()} />

        <InlineNotice tone="neutral" title="Retention and deletion apply to derivatives">
          <p>
            This local slice sets a 30-day access deadline that retries never extend. The retention
            process reconciles expired source media and declared derivatives. You can request earlier
            deletion; delayed or failed physical cleanup remains visible in deletion history.
          </p>
        </InlineNotice>

        {error ? <p className="field-error full" role="alert">{error}</p> : null}
        {!canUpload ? (
          <p className="field-error full" role="note">
            This workspace role cannot upload. An admin or marketer permission is required.
          </p>
        ) : null}
        <div className="form-footer full">
          <p>{saving ? "Uploading through the authorized URL, then validating the staged object…" : "The API revalidates organization, MIME, size and staged-object ownership."}</p>
          <button
            className="button primary"
            type="submit"
            disabled={!file || invalidSize || !rightsAttested || !notice.acknowledged || !uploadAvailable || saving}
          >
            {saving ? "Submitting…" : submission ? "Create revision" : "Create submission"}
          </button>
        </div>
      </form>
    </section>
  );
}
