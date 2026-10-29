"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { InlineNotice, StatusBadge } from "@/components/status";
import { errorMessage, getCampaignReadiness } from "@/lib/api";
import { humanize } from "@/lib/format";
import type { CampaignReadiness, FixtureIdentity } from "@/lib/types";

interface CampaignReadinessPanelProps {
  campaignId: string;
  identity: FixtureIdentity;
  refreshKey?: string;
}

export function CampaignReadinessPanel({
  campaignId,
  identity,
  refreshKey,
}: CampaignReadinessPanelProps) {
  const [brief, setBrief] = useState<CampaignReadiness>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(undefined);
    try {
      setBrief(await getCampaignReadiness(identity, campaignId, signal));
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(errorMessage(caught));
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [campaignId, identity]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => void load(controller.signal));
    return () => controller.abort();
  }, [load, refreshKey]);

  return (
    <section className="readiness-brief" aria-labelledby="readiness-heading" aria-busy={loading}>
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Campaign readiness</p>
          <h2 id="readiness-heading">What needs attention now</h2>
          <p>{brief?.summary ?? "Reading the latest authorized campaign records…"}</p>
        </div>
        <div className="readiness-heading-actions">
          {brief ? <StatusBadge value={brief.ready ? "ready" : brief.blockerCount ? "blocked" : "action_required"} /> : null}
          <button className="button secondary small" type="button" disabled={loading} onClick={() => void load()}>
            {loading ? "Refreshing…" : "Refresh brief"}
          </button>
        </div>
      </div>

      {error ? <InlineNotice tone="danger" title="Readiness brief unavailable"><p>{error}</p></InlineNotice> : null}

      {brief ? (
        <>
          <dl className="readiness-counts" aria-label="Readiness counts">
            <div><dt>Blocking</dt><dd>{brief.blockerCount}</dd></div>
            <div><dt>Next actions</dt><dd>{brief.actionCount}</dd></div>
            <div><dt>Source</dt><dd>Vouch records</dd></div>
          </dl>
          <ol className="readiness-items">
            {brief.items.map((item) => (
              <li className={item.severity} key={item.id}>
                <div>
                  <span className="readiness-category">{humanize(item.category)}</span>
                  <h3>{item.title}</h3>
                  <p>{item.detail}</p>
                </div>
                <Link href={item.citation.href} title={item.citation.label}>{item.actionLabel}</Link>
              </li>
            ))}
          </ol>
          <p className="readiness-limit">{brief.limitations.join(" ")}</p>
        </>
      ) : null}
    </section>
  );
}
