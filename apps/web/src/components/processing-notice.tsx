import { InlineNotice } from "@/components/status";
import { processingNoticeUrl } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ProcessingNotice as Notice } from "@/lib/types";

export function ProcessingNoticeAcknowledgment({ notice, loading, error, acknowledged, disabled, onAcknowledged, onRetry }: {
  notice?: Notice;
  loading: boolean;
  error?: string;
  acknowledged: boolean;
  disabled: boolean;
  onAcknowledged: (value: boolean) => void;
  onRetry: () => void;
}) {
  if (loading) return <div className="full" role="status">Loading the current processing notice before intake...</div>;
  if (!notice) return <div className="full"><InlineNotice tone="warning" title="Processing notice unavailable"><p>{error ?? "Uploads are unavailable until the current notice can be verified."}</p><button className="button secondary small" type="button" onClick={onRetry}>Retry notice loading</button></InlineNotice></div>;
  return (
    <div className="full">
      <InlineNotice tone="neutral" title="Processing notice — draft local only">
        <p><strong>{notice.title}</strong></p>
        {notice.body.split(/\n\s*\n/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
        <p>Version: {notice.version}. Published: {formatDateTime(notice.publishedAt)}.<br />
          Notice hash: <code title={notice.noticeHash}>{notice.noticeHash.slice(0, 12)}…</code></p>
        <p><a href={processingNoticeUrl(notice.version)} target="_blank" rel="noreferrer">Read this immutable notice version (JSON)</a></p>
        <p>This records a workspace processing acknowledgment, not proof of every depicted person’s legal consent.</p>
      </InlineNotice>
      <label className="check-row full">
        <input type="checkbox" checked={acknowledged} required disabled={disabled}
          onChange={(event) => onAcknowledged(event.target.checked)} />
        <span>I acknowledge the processing notice {notice.version} for this workspace’s campaign review.</span>
      </label>
    </div>
  );
}
