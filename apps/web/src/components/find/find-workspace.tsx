"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { CreatorCollection } from "@/components/find/creator-collection";
import { CreatorInspector } from "@/components/find/creator-inspector";
import { useIdentity } from "@/components/identity-context";
import { StatePanel } from "@/components/status";
import { addCreatorToCampaign, errorMessage, getCampaigns, getFindCreators, type CreatorMatchKind, type FindCreator } from "@/lib/api";
import type { Campaign } from "@/lib/types";

type MatchFilter = "all" | Exclude<CreatorMatchKind, "unreviewed"> | "unreviewed";

export function FindWorkspace() {
  const { identity, workspace, workspaceError, workspaceLoading, reloadWorkspace } = useIdentity();
  const [creators, setCreators] = useState<FindCreator[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [campaignId, setCampaignId] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [match, setMatch] = useState<MatchFilter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [actionError, setActionError] = useState<string>();
  const [actionMessage, setActionMessage] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);

  const reload = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    if (!workspace || workspaceLoading || workspaceError) {
      queueMicrotask(() => setLoading(false));
      return;
    }
    const controller = new AbortController();
    queueMicrotask(() => { setLoading(true); setError(undefined); });
    Promise.all([getFindCreators(identity, {}, controller.signal), getCampaigns(identity, controller.signal)])
      .then(([creatorRows, campaignRows]) => {
        setCreators(creatorRows);
        setCampaigns(campaignRows);
        setSelectedId((current) => creatorRows.some((item) => item.id === current) ? current : creatorRows[0]?.id);
        setCampaignId((current) => campaignRows.some((item) => item.id === current) ? current : campaignRows[0]?.id ?? "");
      })
      .catch((caught) => { if (!controller.signal.aborted) setError(errorMessage(caught)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [identity, revision, workspace, workspaceError, workspaceLoading]);

  const categories = useMemo(
    () => [...new Set(creators.flatMap((creator) => creator.evidence.map((item) => item.category)).filter(Boolean))].sort(),
    [creators],
  );
  const visibleCreators = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return creators.filter((creator) => {
      const evidence = creator.evidence;
      const matchesText = !needle || [creator.name, creator.handle, ...evidence.flatMap((item) => [item.category, item.description, item.sourceLabel])]
        .join(" ").toLocaleLowerCase().includes(needle);
      const matchesCategory = category === "all" || evidence.some((item) => item.category === category);
      const matchesKind = match === "all"
        || (match === "unreviewed" ? !evidence.length || evidence.some((item) => item.matchKind === "unreviewed") : evidence.some((item) => item.matchKind === match));
      return matchesText && matchesCategory && matchesKind;
    });
  }, [category, creators, match, query]);
  const selected = creators.find((item) => item.id === selectedId);
  const canMutate = Boolean(workspace?.roles.some((role) => role === "admin" || role === "marketer"));

  const addToCampaign = async (evidenceId: string) => {
    if (!selected || !campaignId) return;
    setBusy(true); setActionError(undefined); setActionMessage(undefined);
    try {
      const assignment = await addCreatorToCampaign(
        identity,
        campaignId,
        selected.id,
        evidenceId,
      );
      setCampaigns((current) => current.map((campaign) => campaign.id === campaignId
        ? { ...campaign, creatorIds: [...new Set([...campaign.creatorIds, assignment.creatorId])] }
        : campaign));
      setActionMessage(assignment.created
        ? `${selected.name} was added to the selected campaign roster.`
        : `${selected.name} is already on this roster with the selected evidence.`);
    } catch (caught) {
      setActionError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  if (workspaceLoading) return <StatePanel kind="loading" title="Opening Find"><p>Verifying your active workspace…</p></StatePanel>;
  if (workspaceError || !workspace) return <StatePanel kind="error" title="Find unavailable" action={<button className="button secondary" onClick={reloadWorkspace}>Try again</button>}><p>{workspaceError ?? "No active workspace was returned for this identity."}</p></StatePanel>;

  return (
    <div className="page-stack find-workspace">
      <header className="find-page-header">
        <div><p className="eyebrow">Vouch Find · Curated collection</p><h1>Discover creators through evidence.</h1><p className="lede">Review tenant-owned proof, permission and match scope before adding a creator to a campaign. This is not a broad social-platform search.</p></div>
        <dl><div><dt>Collection</dt><dd>{loading || error ? "—" : creators.length}</dd><small>workspace-scoped creators</small></div><div><dt>Campaigns</dt><dd>{loading || error ? "—" : campaigns.length}</dd><small>loaded roster destinations</small></div></dl>
      </header>

      {error ? <StatePanel kind="error" title="Creator collection could not be loaded" action={<button className="button secondary" onClick={reload}>Retry</button>}><p>{error}</p></StatePanel> : null}

      <section className="find-collection" aria-labelledby="find-collection-heading">
        <div className="section-heading"><div><p className="eyebrow">Authorized discovery</p><h2 id="find-collection-heading">Creator collection</h2></div><span className="find-result-count" aria-live="polite">{loading ? "Loading…" : `${visibleCreators.length} of ${creators.length}`}</span></div>
        <div className="find-toolbar">
          <label className="field find-search" htmlFor="find-query"><span>Search evidence</span><input id="find-query" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Creator, category or proof source" /></label>
          <label className="field" htmlFor="find-category"><span>Category</span><select id="find-category" value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
          <label className="field" htmlFor="find-match"><span>Match scope</span><select id="find-match" value={match} onChange={(event) => setMatch(event.target.value as MatchFilter)}><option value="all">All evidence</option><option value="exact_product">Exact product evidence</option><option value="category_relevance">Category relevance</option><option value="unreviewed">Unreviewed</option></select></label>
        </div>

        {loading ? <StatePanel kind="loading" title="Loading curated creators"><p>Reading organization-scoped evidence and permissions…</p></StatePanel>
          : creators.length === 0 ? <StatePanel kind="empty" title="No creators in this curated collection"><p>Add a rights-cleared creator and proof record before using Find.</p></StatePanel>
            : visibleCreators.length === 0 ? <StatePanel kind="empty" title="No candidates in this collection match your filters"><p>Clear a filter to inspect the rest of this curated collection.</p><button className="button secondary" onClick={() => { setQuery(""); setCategory("all"); setMatch("all"); }}>Clear filters</button></StatePanel>
              : <div className="find-layout"><CreatorCollection creators={visibleCreators} selectedId={selectedId} onSelect={(creatorId) => { setSelectedId(creatorId); setActionError(undefined); setActionMessage(undefined); }} />{selected ? <CreatorInspector key={`${selected.id}:${campaignId}`} creator={selected} campaigns={campaigns} campaignId={campaignId} organizationName={workspace.name} canMutate={canMutate} busy={busy} actionError={actionError} actionMessage={actionMessage} onCampaignChange={(value) => { setCampaignId(value); setActionError(undefined); setActionMessage(undefined); }} onAdd={(evidenceId) => void addToCampaign(evidenceId)} /> : null}</div>}
      </section>
    </div>
  );
}
