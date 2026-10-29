import { StatusBadge } from "@/components/status";
import type { Capability, CapabilityStatus } from "@/lib/types";

const FAMILY_PLAN = [
  { family: "Spark", role: "Visual reasoning and rule-mapped Check evidence" },
  { family: "Voice Transcribe", role: "Timestamped speech evidence" },
  { family: "SAM", role: "Product/concept evidence with sampling limits" },
  { family: "Image", role: "Conditional eyewear preview" },
  { family: "Wonder", role: "Bounded, cited campaign evidence dossier" },
] as const;

function normalizedFamily(value: string): string {
  const lower = value.toLowerCase();
  if (lower.includes("spark") || lower.includes("reason")) return "Spark";
  if (lower.includes("voice") || lower.includes("transcrib")) return "Voice Transcribe";
  if (lower.includes("sam") || lower.includes("segment")) return "SAM";
  if (lower.includes("image") || lower.includes("try")) return "Image";
  if (lower.includes("wonder") || lower.includes("dossier")) return "Wonder";
  return value;
}

export function CapabilityPanel({
  capabilities,
  market,
}: {
  capabilities: Capability[];
  market: string;
}) {
  const isIndia = /^(in|india)$/i.test(market.trim());

  return (
    <section className="capability-panel" aria-labelledby="capability-heading">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Provider readiness</p>
          <h2 id="capability-heading">Five purposeful model roles</h2>
        </div>
        <span className="text-meta">Market: {market || "Not selected"}</span>
      </div>

      <ul className="capability-list">
        {FAMILY_PLAN.map((planned) => {
          const capability = capabilities.find(
            (candidate) => normalizedFamily(candidate.family) === planned.family,
          );
          const policyRestricted = planned.family === "Image" && isIndia;
          const status: CapabilityStatus = policyRestricted
            ? "policy_restricted"
            : capability?.status ?? "not_configured";
          const reason = policyRestricted
            ? "Muse Image is restricted for India operator/end-user contexts. No image upload or live call is offered."
            : capability?.reason ?? "No capability record was returned for this workspace.";
          return (
            <li key={planned.family}>
              <div>
                <strong>{planned.family === "Image" ? "Image · Muse Image" : planned.family}</strong>
                <span>{capability?.role ?? planned.role}</span>
              </div>
              <StatusBadge value={status} />
              <details>
                <summary>Why this status</summary>
                <p>{reason}</p>
              </details>
            </li>
          );
        })}
      </ul>

      <p className="panel-footnote">
        Fixture coverage proves this application workflow only. Live access, quality, cost and
        regional eligibility remain separate gates.
      </p>
    </section>
  );
}
