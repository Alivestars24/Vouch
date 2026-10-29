"use client";

import { useEffect, useState } from "react";

import { useIdentity } from "@/components/identity-context";
import { errorMessage, getStorageUsage, type StorageUsage } from "@/lib/api";
import type { FixtureIdentity } from "@/lib/types";

import "./storage-usage.css";

function megabytes(bytes: number) {
  return `${(bytes / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 2 })} MB`;
}

function WorkspaceStorage({ identity }: { identity: FixtureIdentity }) {
  const [usage, setUsage] = useState<StorageUsage>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      setLoading(true);
      setError(undefined);
      setUsage(undefined);
    });
    void getStorageUsage(identity, controller.signal).then((value) => {
      if (!controller.signal.aborted) setUsage(value);
    }).catch((caught) => {
      if (!controller.signal.aborted) setError(errorMessage(caught));
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [identity, revision]);

  const charged = usage ? usage.used_bytes + usage.reserved_bytes + usage.pending_cleanup_bytes : 0;
  return (
    <section className="storage-usage" aria-label="Workspace storage" aria-busy={loading}>
      <div className="storage-heading"><h2>Space for your drafts</h2><span aria-hidden="true">↗</span></div>
      {loading ? <p role="status">Reading storage usage…</p> : error ? (
        <p role="alert">{error}</p>
      ) : usage ? <>
        <p className="storage-total"><strong>{megabytes(charged)}</strong><span> of {megabytes(usage.limit_bytes)} allocated</span></p>
        <meter min={0} max={usage.limit_bytes} value={Math.min(charged, usage.limit_bytes)}
          aria-label="Workspace storage allowance in use" aria-valuetext={`${megabytes(charged)} of ${megabytes(usage.limit_bytes)} allocated`} />
        <dl>
          <div><dt>Stored originals</dt><dd>{megabytes(usage.used_bytes)}</dd></div>
          <div><dt>Upload reservations</dt><dd>{megabytes(usage.reserved_bytes)}</dd></div>
          <div><dt>Awaiting cleanup</dt><dd>{megabytes(usage.pending_cleanup_bytes)}</dd></div>
        </dl>
        <p>{usage.storage_backend === "supabase" ? "Private files · original quality" : "Fixture files · local database"}</p>
        {usage.available_bytes < usage.max_upload_bytes ? <p className="field-error" role="status">
          New uploads are paused. Delete unused drafts and wait for confirmed cleanup to free space.
        </p> : null}
        <details><summary>How space is counted</summary><p>
          Each pending upload reserves {megabytes(usage.max_upload_bytes)} until its stored size is confirmed.
          Failed or expired uploads can retain a reservation until cleanup finishes. Files keep their exact
          bytes for review; ZIP archives are not accepted. This workspace allowance is separate from
          the Supabase project&apos;s total storage and database limits.
        </p></details>
      </> : null}
      <button type="button" className="button secondary small" disabled={loading} onClick={() => setRevision((value) => value + 1)}>
        {error ? "Retry storage usage" : "Refresh storage usage"}
      </button>
    </section>
  );
}

export function StorageUsagePanel() {
  const { identity } = useIdentity();
  return <WorkspaceStorage key={identity.key} identity={identity} />;
}
