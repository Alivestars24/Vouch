"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { CapabilityPanel } from "@/components/capability-panel";
import { useIdentity } from "@/components/identity-context";
import { StatePanel, StatusBadge } from "@/components/status";
import { StorageUsagePanel } from "@/components/storage-usage";
import { WorkspaceOverview } from "@/components/workspace-overview";
import {
  createCampaign,
  errorMessage,
  getCatalog,
  getCampaigns,
  getCapabilities,
} from "@/lib/api";
import { formatDateTime, humanize } from "@/lib/format";
import type {
  Campaign,
  Capability,
  CatalogCreator,
  CatalogProduct,
  RulePackVersion,
} from "@/lib/types";

interface FormState {
  name: string;
  objective: string;
  market: string;
  productId: string;
  rulePackVersionId: string;
  creatorIds: string[];
}

const INITIAL_FORM: FormState = {
  name: "",
  objective: "Review an authorized creator launch draft before publication",
  market: "IN",
  productId: "",
  rulePackVersionId: "",
  creatorIds: [],
};

export function CampaignTable({ campaigns }: { campaigns: Campaign[] }) {
  return (
    <div className="table-scroll">
      <table className="campaign-table">
        <caption className="sr-only">Campaigns in the selected workspace</caption>
        <thead>
          <tr>
            <th scope="col">Campaign</th>
            <th scope="col">Market</th>
            <th scope="col">Review basis</th>
            <th scope="col">Next action</th>
            <th scope="col"><span className="sr-only">Open</span></th>
          </tr>
        </thead>
        <tbody>
          {campaigns.map((campaign) => (
            <tr key={campaign.id}>
              <td>
                <div className="campaign-identity">
                  <span className="campaign-monogram" aria-hidden="true">{campaign.name.trim().charAt(0) || "V"}</span>
                  <span>
                    <strong>{campaign.name}</strong>
                    <small>{campaign.brandName}{campaign.productName ? ` · ${campaign.productName}` : ""}</small>
                  </span>
                </div>
                {campaign.createdAt ? <small>Created {formatDateTime(campaign.createdAt)}</small> : null}
              </td>
              <td data-label="Market"><span className="market-code">{campaign.market}</span></td>
              <td data-label="Review basis">
                <StatusBadge value={campaign.status} />
                <small>
                  {campaign.pinnedRulePack
                    ? `${campaign.pinnedRulePack.name} ${campaign.pinnedRulePack.version} · ${humanize(campaign.pinnedRulePack.reviewStatus)}`
                    : "Choose a version before Check"}
                </small>
              </td>
              <td data-label="Next action">
                {campaign.currentActions[0] ?? "Upload a draft to start review"}
              </td>
              <td>
                <Link className="button secondary small" href={`/campaigns/${campaign.id}`}>
                  Open<span className="sr-only"> {campaign.name}</span>
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CreateCampaignForm({
  allowed,
  onCreated,
}: {
  allowed: boolean;
  onCreated: (campaign: Campaign) => void;
}) {
  const { identity } = useIdentity();
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [creators, setCreators] = useState<CatalogCreator[]>([]);
  const [rulePacks, setRulePacks] = useState<RulePackVersion[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    void getCatalog(identity, controller.signal)
      .then((catalog) => {
        setProducts(catalog.products);
        setCreators(catalog.creators);
        setRulePacks(catalog.rulePacks);
        setForm((current) => ({
          ...current,
          productId: current.productId || catalog.products[0]?.id || "",
          rulePackVersionId: current.rulePackVersionId || catalog.rulePacks[0]?.id || "",
          creatorIds: current.creatorIds.length
            ? current.creatorIds
            : catalog.creators[0]?.id
              ? [catalog.creators[0].id]
              : [],
        }));
      })
      .catch((caught) => {
        if (!controller.signal.aborted) setError(errorMessage(caught));
      });
    return () => controller.abort();
  }, [identity]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!allowed || saving) return;
    setSaving(true);
    setError(undefined);
    try {
      const campaign = await createCampaign(identity, form);
      onCreated(campaign);
      setForm((current) => ({
        ...INITIAL_FORM,
        market: current.market,
        productId: current.productId,
        rulePackVersionId: current.rulePackVersionId,
        creatorIds: current.creatorIds,
      }));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="campaign-form" onSubmit={submit} aria-describedby="campaign-form-note">
      <div className="field wide">
        <label htmlFor="campaign-name">Campaign name</label>
        <input
          id="campaign-name"
          name="name"
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
          placeholder="Monsoon Frames launch"
          required
          maxLength={120}
          disabled={!allowed || saving}
        />
      </div>
      <div className="field">
        <label htmlFor="campaign-product">Product</label>
        <select
          id="campaign-product"
          value={form.productId}
          onChange={(event) => setForm({ ...form, productId: event.target.value })}
          required
          disabled={!allowed || saving}
        >
          {products.map((product) => (
            <option key={product.id} value={product.id}>{product.name} ({product.sku})</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="campaign-pack">Rule pack version</label>
        <select
          id="campaign-pack"
          value={form.rulePackVersionId}
          onChange={(event) => setForm({ ...form, rulePackVersionId: event.target.value })}
          required
          disabled={!allowed || saving}
        >
          {rulePacks.map((pack) => (
            <option key={pack.id} value={pack.id}>{pack.name} {pack.version} ({humanize(pack.status)})</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="campaign-creator">Authorized creator</label>
        <select
          id="campaign-creator"
          value={form.creatorIds[0] ?? ""}
          onChange={(event) => setForm({ ...form, creatorIds: [event.target.value] })}
          required
          disabled={!allowed || saving}
        >
          {creators.map((creator) => (
            <option key={creator.id} value={creator.id}>{creator.name} ({creator.handle})</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="campaign-market">Primary market</label>
        <select
          id="campaign-market"
          name="market"
          value={form.market}
          onChange={(event) => setForm({ ...form, market: event.target.value })}
          disabled={!allowed || saving}
        >
          <option value="IN">India</option>
          <option value="US">United States</option>
          <option value="GB">United Kingdom</option>
        </select>
      </div>
      <div className="field full">
        <label htmlFor="campaign-objective">Objective</label>
        <textarea
          id="campaign-objective"
          name="objective"
          value={form.objective}
          onChange={(event) => setForm({ ...form, objective: event.target.value })}
          rows={3}
          required
          disabled={!allowed || saving}
        />
      </div>
      <div className="form-footer full">
        <p id="campaign-form-note">
          The API verifies organization membership. Rule packs remain versioned and draft packs are
          not legally reviewed.
        </p>
        <button className="button primary" type="submit" disabled={
          !allowed || saving || !form.productId || !form.rulePackVersionId || !form.creatorIds.length
        }>
          {saving ? "Creating…" : "Create campaign"}
        </button>
      </div>
      {!allowed ? (
        <p className="field-error full" role="note">
          An admin or marketer role is required to create a campaign.
        </p>
      ) : null}
      {error ? <p className="field-error full" role="alert">{error}</p> : null}
    </form>
  );
}

export function WorkspaceHome() {
  const router = useRouter();
  const { identity, workspace, workspaceLoading, workspaceError, reloadWorkspace } = useIdentity();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [reloadToken, setReloadToken] = useState(0);
  const [query, setQuery] = useState("");
  const createDrawer = useRef<HTMLDetailsElement>(null);

  const load = useCallback(() => setReloadToken((value) => value + 1), []);

  useEffect(() => {
    if (!workspace || workspaceLoading || workspaceError) {
      queueMicrotask(() => setLoading(false));
      return;
    }
    const controller = new AbortController();
    queueMicrotask(() => {
      setLoading(true);
      setError(undefined);
    });
    Promise.all([
      getCampaigns(identity, controller.signal),
      getCapabilities(identity, "IN", controller.signal),
    ])
      .then(([campaignRows, capabilityRows]) => {
        setCampaigns(campaignRows);
        setCapabilities(capabilityRows);
      })
      .catch((caught) => {
        if (!controller.signal.aborted) setError(errorMessage(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [identity, reloadToken, workspace, workspaceError, workspaceLoading]);

  const canCreate = Boolean(
    workspace?.roles.some((role) => role === "admin" || role === "marketer"),
  );
  const actionCount = useMemo(
    () => campaigns.reduce((total, campaign) => total + campaign.currentActions.length, 0),
    [campaigns],
  );
  const visibleCampaigns = useMemo(() => {
    const search = query.trim().toLocaleLowerCase();
    return campaigns.filter((campaign) => `${campaign.name} ${campaign.brandName} ${campaign.market}`.toLocaleLowerCase().includes(search));
  }, [campaigns, query]);

  const openCreateCampaign = useCallback(() => {
    const drawer = createDrawer.current;
    if (!drawer) return;
    drawer.open = true;
    drawer.scrollIntoView({ block: "start" });
    requestAnimationFrame(() => drawer.querySelector<HTMLInputElement>("#campaign-name")?.focus());
  }, []);

  if (workspaceLoading) {
    return (
      <StatePanel kind="loading" title="Opening workspace">
        <p>Verifying your identity and organization membership…</p>
      </StatePanel>
    );
  }

  if (workspaceError || !workspace) {
    return (
      <StatePanel
        kind="error"
        title="Workspace unavailable"
        action={<button className="button secondary" onClick={reloadWorkspace}>Try again</button>}
      >
        <p>{workspaceError ?? "No active workspace was returned for this identity."}</p>
      </StatePanel>
    );
  }

  return (
    <div className="page-stack">
      <WorkspaceOverview
        workspaceName={workspace.name}
        campaigns={campaigns}
        loading={loading}
        error={error}
        actionCount={actionCount}
        onCreate={openCreateCampaign}
      />

      {error ? (
        <StatePanel
          kind="error"
          title="Campaign data could not be loaded"
          action={<button className="button secondary" onClick={load}>Retry</button>}
        >
          <p>{error}</p>
        </StatePanel>
      ) : null}

      <div className="workspace-grid">
        <section className="primary-column" id="campaigns" aria-labelledby="campaigns-heading">
          <div className="section-heading">
            <div>
              <h2 id="campaigns-heading">Review pipeline</h2>
            </div>
            <StatusBadge value="fixture" label="Sample environment" />
          </div>

          <div className="workspace-toolbar">
            <label className="field"><span className="sr-only">Search loaded campaigns</span><input type="search" placeholder="Search campaigns…" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
            <span aria-live="polite">{loading ? "Loading…" : error ? "Campaign data unavailable" : `${visibleCampaigns.length} of ${campaigns.length} loaded`}</span>
          </div>

          {loading ? (
            <StatePanel kind="loading" title="Loading campaigns">
              <p>Reading organization-scoped campaign records…</p>
            </StatePanel>
          ) : campaigns.length === 0 ? (
            <StatePanel kind="empty" title="No campaigns in this workspace">
              <p>Create a campaign below, then upload an authorized draft to start review.</p>
            </StatePanel>
          ) : visibleCampaigns.length === 0 ? (
            <StatePanel kind="empty" title="No matching campaigns"><p>Try another campaign name, brand or market.</p><button className="button secondary" onClick={() => setQuery("")}>Clear search</button></StatePanel>
          ) : (
            <CampaignTable campaigns={visibleCampaigns} />
          )}

          <details className="create-drawer" ref={createDrawer}>
            <summary>
              <span>Create a campaign</span>
              <small>Organization-scoped, version-aware setup</small>
            </summary>
            <CreateCampaignForm
              allowed={canCreate}
              onCreated={(campaign) => router.push(`/campaigns/${campaign.id}`)}
            />
          </details>
        </section>

        <aside className="secondary-column" aria-label="Capability readiness">
          <StorageUsagePanel />
          <CapabilityPanel capabilities={capabilities} market="IN" />
          <section className="trust-note" aria-labelledby="trust-heading">
            <p className="eyebrow">Trust boundary</p>
            <h2 id="trust-heading">Human approval stays explicit</h2>
            <p>
              Fixture findings are decision support. They do not publish content, certify legal
              compliance or establish live provider access.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
