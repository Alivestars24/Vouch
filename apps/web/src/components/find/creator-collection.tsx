import { humanize } from "@/lib/format";
import type { CreatorEvidence, FindCreator } from "@/lib/api";

function primaryEvidence(creator: FindCreator): CreatorEvidence | undefined {
  return creator.evidence.find((item) => item.matchKind === "exact_product") ?? creator.evidence[0];
}

function evidenceLabel(evidence?: CreatorEvidence): string {
  if (!evidence || evidence.matchKind === "unreviewed") return "Match unreviewed";
  return evidence.matchKind === "exact_product" ? "Exact product evidence" : "Category relevance";
}

function readableDate(value?: string): string {
  if (!value) return "Timestamp not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Timestamp unavailable"
    : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium" }).format(date);
}

export function CreatorCollection({
  creators,
  selectedId,
  onSelect,
}: {
  creators: FindCreator[];
  selectedId?: string;
  onSelect: (creatorId: string) => void;
}) {
  return (
    <ul className="find-results-list" aria-label="Creator candidates">
      {creators.map((creator) => {
        const evidence = primaryEvidence(creator);
        const timestamp = evidence?.capturedAt ?? creator.evidenceTimestamp;
        return (
          <li key={creator.id}>
            <button
              type="button"
              className="creator-result"
              aria-pressed={selectedId === creator.id}
              onClick={() => onSelect(creator.id)}
            >
              <span className="creator-result-heading">
                <span className="creator-monogram" aria-hidden="true">
                  {creator.name.slice(0, 1).toLocaleUpperCase()}
                </span>
                <span>
                  <strong>{creator.name}</strong>
                  <small>{creator.handle || "Handle not recorded"}</small>
                </span>
                <span className={`find-match ${evidence?.matchKind ?? "unreviewed"}`}>
                  {evidenceLabel(evidence)}
                </span>
              </span>
              <span className="creator-proof-summary">
                {evidence?.description ?? "No authorized proof is attached to this creator yet."}
              </span>
              <span className="creator-result-meta">
                <span>{evidence?.category ?? "Uncategorized"}</span>
                <span>{humanize(evidence?.evidenceMode ?? "unreviewed")}</span>
                <span>{readableDate(timestamp)}</span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
