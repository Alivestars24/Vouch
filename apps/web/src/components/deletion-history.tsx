"use client";

import { useCallback, useEffect, useId, useState } from "react";

import { useIdentity } from "@/components/identity-context";
import { InlineNotice, StatusBadge } from "@/components/status";
import { errorMessage, getDeletionRequests, requestDeletion } from "@/lib/api";
import { formatDateTime, humanize } from "@/lib/format";
import type { DeletionReceipt, FixtureIdentity } from "@/lib/types";

interface DeletionHistoryProps {
  campaignId: string;
  canRetry: boolean;
  refreshKey?: string;
  onReceiptChange?: (receipt: DeletionReceipt) => void;
  onHistoryLoaded?: (receipts: DeletionReceipt[]) => void;
}

export function DeletionHistory(props: DeletionHistoryProps) {
  const { identity } = useIdentity();
  return <DeletionHistoryPanel key={`${identity.key}:${identity.organizationId}:${props.campaignId}`} identity={identity} {...props} />;
}

function DeletionHistoryPanel({
  campaignId,
  canRetry,
  refreshKey,
  onReceiptChange,
  onHistoryLoaded,
  identity,
}: DeletionHistoryProps & { identity: FixtureIdentity }) {
  const headingId = useId();
  const [receipts, setReceipts] = useState<DeletionReceipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [retryingId, setRetryingId] = useState<string>();

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(undefined);
    try {
      const items = await getDeletionRequests(identity, campaignId, signal);
      if (!signal?.aborted) {
        setReceipts(items);
        onHistoryLoaded?.(items);
      }
    } catch (caught) {
      if (!signal?.aborted) setError(errorMessage(caught));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [campaignId, identity, onHistoryLoaded]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => void load(controller.signal));
    return () => controller.abort();
  }, [load, refreshKey]);

  async function retry(receipt: DeletionReceipt) {
    if (!canRetry || retryingId) return;
    setRetryingId(receipt.id);
    setError(undefined);
    try {
      const updated = await requestDeletion(identity, {
        resourceType: receipt.resourceType,
        resourceId: receipt.resourceId,
      });
      setReceipts((current) => current.map((item) => item.id === updated.id ? updated : item));
      onReceiptChange?.(updated);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setRetryingId(undefined);
    }
  }

  return (
    <section className="context-card" aria-labelledby={headingId}>
      <p className="eyebrow">Durable privacy record</p>
      <h2 id={headingId}>Deletion history</h2>
      <p>The latest 50 campaign receipts survive page reloads. Refresh to check background cleanup.</p>
      <button className="button secondary small" disabled={loading || Boolean(retryingId)} onClick={() => void load()}>
        {loading ? "Loading deletion history..." : "Refresh deletion history"}
      </button>
      {error ? <InlineNotice tone="danger" title="Deletion history unavailable"><p>{error}</p></InlineNotice> : null}
      <div aria-busy={loading}>
        {!loading && !error && receipts.length === 0 ? <p>No deletion requests recorded for this campaign.</p> : null}
        {receipts.map((receipt) => (
          <details key={receipt.id}>
            <summary>
              {humanize(receipt.resourceType)} {receipt.resourceId.slice(0, 8)} <StatusBadge value={receipt.status} />
            </summary>
            <p>{receipt.notice}</p>
            <p>Requested by: {receipt.requestedByKind === "retention" ? "Retention system" : "Workspace member"}.<br />
              Created: {formatDateTime(receipt.createdAt)}.<br />
              Attempts: {receipt.attemptCount}. Automatic limit: {receipt.maxAttempts}.</p>
            {receipt.attemptCount > receipt.maxAttempts ? <p>Additional attempts were explicitly requested by a workspace member; automatic retries remain capped.</p> : null}
            <ul>{receipt.destinations.map((item) => <li key={item.destination}>{humanize(item.destination)} — {humanize(item.status)}</li>)}</ul>
            {receipt.completedAt ? <p>Completed: {formatDateTime(receipt.completedAt)}</p> : null}
            {receipt.status === "failed" ? <p>Automatic cleanup stopped after its retry limit. Source access remains blocked.</p> : null}
            {receipt.status !== "completed" && receipt.status !== "failed" && receipt.retryAfter ? <p>Automatic retry scheduled: {formatDateTime(receipt.retryAfter)}</p> : null}
            {receipt.lastErrorCode ? <p>Last cleanup error: {humanize(receipt.lastErrorCode)}</p> : null}
            {receipt.status !== "completed" ? canRetry ? (
              <button className="button secondary small" disabled={loading || Boolean(retryingId)} onClick={() => void retry(receipt)}>
                {retryingId === receipt.id ? "Retrying cleanup..." : "Retry cleanup"}
              </button>
            ) : <p>An admin or marketer can retry incomplete cleanup.</p> : null}
            <p>Receipt: <code>{receipt.id.slice(0, 8)}</code></p>
          </details>
        ))}
      </div>
    </section>
  );
}
