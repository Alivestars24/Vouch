import Link from "next/link";

import type { Campaign } from "@/lib/types";

function HeroArtwork({ campaign }: { campaign?: Campaign }) {
  return (
    <div className="hero-artwork" aria-hidden="true">
      <svg className="hero-artwork-shape" viewBox="0 0 680 520" fill="none">
        <path d="M88 423C-1 329 35 126 180 71c135-51 223 82 344 38 97-36 152 61 96 168-59 113-180 205-318 205-85 0-157-18-214-59Z" fill="var(--color-blue-soft)" />
        <path d="M394 40c81-30 181 2 220 75 42 79-10 183-99 203-80 19-140-34-168-103-29-73-24-149 47-175Z" fill="var(--color-brand-soft)" />
        <path d="M467 71c71 8 126 56 145 121-43 10-84 5-120-14-38-20-66-53-84-96 19-9 39-13 59-11Z" fill="var(--color-brand)" opacity=".9" />
      </svg>
      <div className="hero-creator-frame">
        <div className="hero-creator-silhouette">
          <span className="hero-creator-head" />
          <span className="hero-creator-body" />
        </div>
        <div className="hero-frame-caption">
          <span>Creator draft</span>
          <strong>{campaign ? "Loaded campaign focus" : "Ready for your first campaign"}</strong>
        </div>
      </div>
      <div className="hero-product-card">
        <span className="hero-bottle"><i /></span>
        <div><small>Product</small><strong>{campaign?.productName ?? "Campaign product"}</strong></div>
      </div>
      <div className="hero-proof-card">
        <span className="hero-proof-icon">✓</span>
        <div><small>Decision model</small><strong>Evidence + human review</strong></div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  note,
  ariaLabel,
}: {
  label: string;
  value: string;
  note: string;
  ariaLabel?: string;
}) {
  return (
    <div aria-label={ariaLabel}>
      <dt>{label}</dt>
      <dd>{value}</dd>
      <small>{note}</small>
    </div>
  );
}

export function WorkspaceOverview({
  workspaceName,
  campaigns,
  loading,
  error,
  actionCount,
  onCreate,
}: {
  workspaceName: string;
  campaigns: Campaign[];
  loading: boolean;
  error?: string;
  actionCount: number;
  onCreate: () => void;
}) {
  const unavailable = loading || Boolean(error);
  const markets = new Set(campaigns.map((campaign) => campaign.market).filter(Boolean)).size;
  const displayValue = (value: number) => unavailable ? "—" : value.toLocaleString();

  return (
    <>
      <section className="workspace-hero" aria-labelledby="workspace-title">
        <div className="workspace-hero-copy">
          <p className="eyebrow">Welcome back, {workspaceName}</p>
          <h1 id="workspace-title">Creator work,<br /><em>cleared with confidence.</em></h1>
          <p className="lede">
            Build the campaign, review the evidence and keep every approval bound to the exact
            creator draft your team saw.
          </p>
          <div className="hero-actions">
            <button
              aria-label="Start campaign setup"
              className="button primary"
              type="button"
              onClick={onCreate}
            >
              Create campaign <span aria-hidden="true">→</span>
            </button>
            <Link className="button quiet" href="#campaigns">Review campaigns</Link>
          </div>
          <dl className="hero-metrics" aria-label="Loaded workspace summary">
            <Metric label="Campaigns" value={displayValue(campaigns.length)} note="loaded in this workspace" />
            <Metric
              label="Next steps"
              value={displayValue(actionCount)}
              note="from loaded campaigns"
              ariaLabel={unavailable ? "Campaign actions unavailable" : `${actionCount} campaign actions`}
            />
            <Metric label="Markets" value={displayValue(markets)} note="represented in loaded work" />
          </dl>
        </div>
        <HeroArtwork campaign={campaigns[0]} />
      </section>

      <section className="module-overview" aria-label="Vouch product modules">
        <Link className="module-card find-module" href="/find">
          <div className="module-card-top"><span>01</span><small>Curated creators</small></div>
          <h2>Vouch Find</h2>
          <p>Explore curated creators using their available portfolio evidence.</p>
          <div className="module-visual creator-cluster" aria-hidden="true"><i /><i /><i /></div>
        </Link>
        <Link className="module-card check-module" href="#campaigns">
          <div className="module-card-top"><span>02</span><small>Fixture analysis</small></div>
          <h2>Vouch Check</h2>
          <p>Review drafts and fixture findings before a human decision. Live media analysis is not yet enabled.</p>
          <div className="module-visual check-sheet" aria-hidden="true"><i /><i /><i /></div>
        </Link>
        <article className="module-card try-module">
          <div className="module-card-top"><span>03</span><small>Unavailable in India</small></div>
          <h2>Vouch Try</h2>
          <p>Product preview is unavailable in India because the intended image model is restricted there.</p>
          <div className="module-visual split-preview" aria-hidden="true"><i /><i /></div>
        </article>
        <Link className="module-card track-module" href="/track">
          <div className="module-card-top"><span>04</span><small>Test data</small></div>
          <h2>Vouch Track</h2>
          <p>Explore test outcomes. Real orders and revenue are not connected yet.</p>
          <svg className="module-chart" viewBox="0 0 180 56" aria-hidden="true"><path d="M2 49c22 0 28-12 43-12 17 0 22 7 39-2 20-11 26-25 46-18 19 6 27-14 48-15" /><path d="M2 55h176" /></svg>
        </Link>
      </section>
    </>
  );
}
