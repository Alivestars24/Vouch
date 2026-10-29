"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useIdentity } from "@/components/identity-context";
import { StatePanel } from "@/components/status";
import { TrackOutcomeGraph } from "@/components/track-outcome-graph";
import {
  errorMessage,
  getCampaigns,
  getCampaignTrack,
  getCatalog,
  recordTestOutcomeEvent,
} from "@/lib/api";
import type {
  Campaign,
  CampaignTrack,
  CatalogCreator,
  TrackEnvironmentSummary,
  TrackEventKind,
} from "@/lib/types";

function formatMinor(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(amount / 100);
  } catch {
    return `${currency} ${(amount / 100).toFixed(2)}`;
  }
}

function Summary({ label, summary, live = false }: {
  label: string;
  summary: TrackEnvironmentSummary;
  live?: boolean;
}) {
  const totals = Object.entries(summary.totalsByCurrency);
  return (
    <article className={`track-summary ${live ? "live" : "test"}`}>
      <div className="track-summary-heading">
        <div><p className="eyebrow">{live ? "Connector boundary" : "Demo environment"}</p><h2>{label}</h2></div>
        <span className={`badge ${live ? "neutral" : "warning"}`}>{live ? "No connector" : "Test only"}</span>
      </div>
      {live ? <p className="track-boundary">Live ingestion is not configured. Test events never appear in this panel or in real outcome metrics.</p> : null}
      <dl className="track-metrics">
        <div><dt>Clicks</dt><dd>{summary.clicks}</dd></div>
        <div><dt>Orders</dt><dd>{summary.orders}</dd></div>
        <div><dt>Refunds</dt><dd>{summary.refunds}</dd></div>
        <div><dt>Conversion</dt><dd>{summary.conversionRate === undefined ? "—" : `${(summary.conversionRate * 100).toFixed(1)}%`}</dd></div>
      </dl>
      <div className="track-totals">
        <strong>Order value by currency</strong>
        {totals.length ? totals.map(([currency, total]) => (
          <dl key={currency}>
            <div><dt>Gross</dt><dd>{formatMinor(total.grossMinor, currency)}</dd></div>
            <div><dt>Refunded</dt><dd>{formatMinor(total.refundedMinor, currency)}</dd></div>
            <div><dt>Net</dt><dd>{formatMinor(total.netMinor, currency)}</dd></div>
          </dl>
        )) : <p>No {live ? "live" : "test"} order value recorded.</p>}
      </div>
    </article>
  );
}

export function TrackWorkspace() {
  const { identity, workspace, workspaceError, workspaceLoading, reloadWorkspace } = useIdentity();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [creators, setCreators] = useState<CatalogCreator[]>([]);
  const [campaignId, setCampaignId] = useState("");
  const [report, setReport] = useState<CampaignTrack>();
  const [kind, setKind] = useState<TrackEventKind>("click");
  const [creatorId, setCreatorId] = useState("");
  const [orderId, setOrderId] = useState("");
  const [amountMinor, setAmountMinor] = useState(12500);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [message, setMessage] = useState<string>();

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!workspace) return;
    setLoading(true);
    setError(undefined);
    try {
      const [campaignRows, catalog] = await Promise.all([
        getCampaigns(identity, signal),
        getCatalog(identity, signal),
      ]);
      const selectedId = campaignRows.some((item) => item.id === campaignId)
        ? campaignId
        : campaignRows[0]?.id ?? "";
      setCampaigns(campaignRows);
      setCreators(catalog.creators);
      setCampaignId(selectedId);
      if (!selectedId) setReport(undefined);
      else setReport(await getCampaignTrack(identity, selectedId, signal));
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(errorMessage(caught));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [campaignId, identity, workspace]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => void load(controller.signal));
    return () => controller.abort();
  }, [load]);

  const campaign = campaigns.find((item) => item.id === campaignId);
  const roster = useMemo(
    () => creators.filter((creator) => campaign?.creatorIds.includes(creator.id)),
    [campaign, creators],
  );
  const orders = useMemo(
    () => report?.events.filter(
      (event) => event.environment === "test" && event.eventKind === "order",
    ) ?? [],
    [report],
  );
  const canMutate = Boolean(workspace?.roles.some((role) => role === "admin" || role === "marketer"));
  const selectedCreatorId = roster.some((item) => item.id === creatorId)
    ? creatorId
    : roster[0]?.id ?? "";
  const selectedOrderId = kind === "refund" && !orders.some(
    (item) => item.orderExternalId === orderId,
  )
    ? orders[0]?.orderExternalId ?? ""
    : orderId;

  async function changeCampaign(nextId: string) {
    setCampaignId(nextId);
    setReport(undefined);
    setLoading(true);
    setError(undefined);
    try {
      setReport(await getCampaignTrack(identity, nextId));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  async function recordEvent() {
    if (!campaignId || !selectedCreatorId) return;
    const eventOrderId = kind === "click"
      ? undefined
      : kind === "refund"
        ? selectedOrderId
        : selectedOrderId.trim() || `test-order-${crypto.randomUUID()}`;
    if (kind === "refund" && !eventOrderId) {
      setError("Record a test order before recording its refund.");
      return;
    }
    setBusy(true);
    setError(undefined);
    setMessage(undefined);
    try {
      await recordTestOutcomeEvent(identity, campaignId, {
        creatorId: selectedCreatorId,
        eventKind: kind,
        externalEventId: `test-${kind}-${crypto.randomUUID()}`,
        orderExternalId: eventOrderId,
        amountMinor: kind === "click" ? 0 : amountMinor,
        currency: "INR",
        occurredAt: new Date().toISOString(),
      });
      setReport(await getCampaignTrack(identity, campaignId));
      setOrderId("");
      setMessage(`Test ${kind} recorded. Live metrics were not changed.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  if (workspaceLoading) return <StatePanel kind="loading" title="Opening Track"><p>Verifying your active workspace…</p></StatePanel>;
  if (workspaceError || !workspace) return <StatePanel kind="error" title="Track unavailable" action={<button className="button secondary" onClick={reloadWorkspace}>Try again</button>}><p>{workspaceError ?? "No active workspace was returned for this identity."}</p></StatePanel>;

  return (
    <div className="page-stack track-workspace">
      <header className="track-page-header">
        <div><p className="eyebrow">Vouch Track · test outcome ledger</p><h1>Measure without mixing test and live.</h1><p className="lede">Record deterministic campaign demo events, account for refunds, and keep live commerce empty until a verified connector exists.</p></div>
        <label className="field" htmlFor="track-campaign"><span>Campaign</span><select id="track-campaign" value={campaignId} disabled={loading || !campaigns.length} onChange={(event) => void changeCampaign(event.target.value)}>{campaigns.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
      </header>

      {error ? <StatePanel kind="error" title="Track could not complete the request" action={<button className="button secondary" onClick={() => void load()}>Retry</button>}><p>{error}</p></StatePanel> : null}
      {!loading && !campaigns.length ? <StatePanel kind="empty" title="No campaign to track"><p>Create a campaign before recording test outcomes.</p></StatePanel> : null}
      {loading && !report ? <StatePanel kind="loading" title="Loading campaign outcomes"><p>Reading tenant-scoped test and live ledgers…</p></StatePanel> : null}

      {report ? <>
        <section className="track-summary-grid" aria-label="Environment-separated outcome summaries">
          <Summary label="Test outcomes" summary={report.test} />
          <Summary label="Live outcomes" summary={report.live} live />
        </section>

        <TrackOutcomeGraph summary={report.test} />

        <section className="track-recorder" aria-labelledby="track-recorder-heading">
          <div><p className="eyebrow">Safe demo input</p><h2 id="track-recorder-heading">Record a test event</h2><p>Only admins and marketers can mutate this test ledger. A stable external event ID makes each request idempotent.</p></div>
          <div className="track-recorder-fields">
            <label className="field"><span>Event</span><select value={kind} onChange={(event) => { setKind(event.target.value as TrackEventKind); setOrderId(""); }}><option value="click">Click</option><option value="order">Order</option><option value="refund">Refund</option></select></label>
            <label className="field"><span>Rostered creator</span><select value={selectedCreatorId} onChange={(event) => setCreatorId(event.target.value)}>{roster.map((creator) => <option value={creator.id} key={creator.id}>{creator.name}</option>)}</select></label>
            {kind === "order" ? <label className="field"><span>Order ID (optional)</span><input value={orderId} onChange={(event) => setOrderId(event.target.value)} placeholder="Generated when blank" /></label> : null}
            {kind === "refund" ? <label className="field"><span>Test order</span><select value={selectedOrderId} onChange={(event) => setOrderId(event.target.value)}><option value="">Select an order</option>{orders.map((event) => <option key={event.id} value={event.orderExternalId}>{event.orderExternalId}</option>)}</select></label> : null}
            {kind !== "click" ? <label className="field"><span>Amount (paise)</span><input type="number" min={kind === "refund" ? 1 : 0} step={1} value={amountMinor} onChange={(event) => setAmountMinor(Number(event.target.value))} /></label> : null}
            <button className="button primary" disabled={!canMutate || !selectedCreatorId || busy || kind === "refund" && !selectedOrderId} onClick={() => void recordEvent()}>{busy ? "Recording…" : `Record test ${kind}`}</button>
          </div>
          {!canMutate ? <p className="track-help">Viewer and reviewer roles can inspect outcomes but cannot record events.</p> : null}
          {message ? <p className="track-success" role="status">{message}</p> : null}
        </section>

        <section className="track-ledger" aria-labelledby="track-ledger-heading">
          <div className="section-heading"><div><p className="eyebrow">Attribution evidence</p><h2 id="track-ledger-heading">Event ledger</h2></div><span className="find-result-count">{report.events.length} events</span></div>
          <p className="track-freshness">Conversion = attributed orders ÷ attributed clicks. Freshness: {report.freshnessAt ? new Date(report.freshnessAt).toLocaleString() : "no events yet"}.</p>
          {report.events.length ? <div className="table-scroll"><table><thead><tr><th>Environment</th><th>Event</th><th>Order</th><th>Value</th><th>Occurred</th></tr></thead><tbody>{report.events.map((event) => <tr key={event.id}><td><span className={`badge ${event.environment === "test" ? "warning" : "success"}`}>{event.environment}</span></td><td>{event.eventKind}</td><td className="mono">{event.orderExternalId ?? "—"}</td><td>{event.amountMinor ? formatMinor(event.amountMinor, event.currency) : "—"}</td><td>{new Date(event.occurredAt).toLocaleString()}</td></tr>)}</tbody></table></div> : <StatePanel kind="empty" title="No test events yet"><p>Record a click or order to demonstrate the isolated attribution ledger.</p></StatePanel>}
        </section>
      </> : null}
    </div>
  );
}
