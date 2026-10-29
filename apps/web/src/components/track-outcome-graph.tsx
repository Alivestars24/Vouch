import type { TrackEnvironmentSummary } from "@/lib/types";

const BAR_WIDTH = 320;

export function TrackOutcomeGraph({ summary }: { summary: TrackEnvironmentSummary }) {
  const rows = [
    { label: "Attributed clicks", value: summary.clicks, className: "clicks" },
    { label: "Attributed orders", value: summary.orders, className: "orders" },
    { label: "Refund events", value: summary.refunds, className: "refunds" },
  ];
  const maximum = Math.max(1, ...rows.map((row) => row.value));
  const conversion = summary.conversionRate === undefined
    ? "Not available until a click is recorded"
    : `${(summary.conversionRate * 100).toFixed(1)}% of attributed clicks became orders`;

  return (
    <figure className="track-outcome-graph" aria-labelledby="track-graph-heading">
      <figcaption>
        <div>
          <p className="eyebrow">Test attribution shape</p>
          <h2 id="track-graph-heading">From click to order</h2>
        </div>
        <p>{conversion}</p>
      </figcaption>
      <svg
        viewBox="0 0 520 174"
        role="img"
        aria-labelledby="track-graph-title track-graph-description"
      >
        <title id="track-graph-title">Test attribution funnel</title>
        <desc id="track-graph-description">
          Horizontal bars compare attributed test clicks, test orders, and test refund events.
          These values never include live commerce activity.
        </desc>
        {rows.map((row, index) => {
          const y = 18 + index * 52;
          const width = (row.value / maximum) * BAR_WIDTH;
          return (
            <g key={row.label} className={`track-graph-row ${row.className}`}>
              <text x="0" y={y + 19}>{row.label}</text>
              <rect className="track-graph-rail" x="148" y={y} width={BAR_WIDTH} height="28" rx="4" />
              <rect className="track-graph-bar" x="148" y={y} width={width} height="28" rx="4" />
              <text className="track-graph-value" x="504" y={y + 19} textAnchor="end">{row.value}</text>
            </g>
          );
        })}
      </svg>
      <p className="track-graph-note">Test ledger only · exact counts · no projected revenue</p>
    </figure>
  );
}
