import type { ReactNode } from "react";

import { SignalActivity } from "@/components/signal-motion";
import { humanize } from "@/lib/format";
import type { Check } from "@/lib/types";

type Tone = "neutral" | "brand" | "success" | "warning" | "danger";

function toneFor(value: string): Tone {
  if (["approved", "completed", "succeeded", "complete", "ready"].includes(value)) return "success";
  if (
    [
      "partial",
      "unreviewed",
      "changes_requested",
      "fixes_suggested",
      "human_review_required",
      "retry_wait",
      "awaiting_access",
      "configured_unverified",
      "unknown",
    ].includes(value)
  ) {
    return "warning";
  }
  if (
    [
      "failed",
      "rejected",
      "revoked",
      "critical",
      "potentially_blocking",
      "policy_restricted",
      "missing",
      "dead_letter",
      "outcome_unknown",
    ].includes(value)
  ) {
    return "danger";
  }
  if (["running", "queued", "fixture"].includes(value)) return "brand";
  return "neutral";
}

export function StatusBadge({ value, label }: { value: string; label?: string }) {
  const tone = toneFor(value);
  return (
    <span className={`badge ${tone}`}>
      <span className="badge-mark" aria-hidden="true" />
      {label ?? humanize(value)}
    </span>
  );
}

export function StatusTriptych({ check }: { check: Check }) {
  return (
    <section className="status-triptych" aria-labelledby="decision-state-heading">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Decision state</p>
          <h2 id="decision-state-heading">Three states, kept separate</h2>
        </div>
        <StatusBadge value={check.invocationMode} label={`${humanize(check.invocationMode)} result`} />
      </div>
      <dl>
        <div>
          <dt>Analysis lifecycle</dt>
          <dd><StatusBadge value={check.analysisStatus} /></dd>
          <p>Whether evidence processing finished.</p>
        </div>
        <div>
          <dt>Machine assessment</dt>
          <dd><StatusBadge value={check.machineAssessment} /></dd>
          <p>Decision support within observed coverage.</p>
        </div>
        <div>
          <dt>Human review</dt>
          <dd><StatusBadge value={check.reviewStatus} /></dd>
          <p>Recorded reviewer decision for this exact version.</p>
        </div>
      </dl>
    </section>
  );
}

export function StatePanel({
  kind,
  title,
  children,
  action,
}: {
  kind: "loading" | "empty" | "error" | "info";
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section
      className={`state-panel ${kind}`}
      role={kind === "error" ? "alert" : "status"}
      aria-live={kind === "loading" ? "polite" : undefined}
      aria-busy={kind === "loading" || undefined}
    >
      {kind === "loading" ? <SignalActivity status="loading" size={64} /> : (
        <span className="state-symbol" aria-hidden="true">{kind === "error" ? "!" : kind === "empty" ? "○" : "i"}</span>
      )}
      <div>
        <h2>{title}</h2>
        <div className="state-copy">{children}</div>
        {action ? <div className="state-action">{action}</div> : null}
      </div>
    </section>
  );
}

export function InlineNotice({
  tone = "neutral",
  title,
  children,
}: {
  tone?: Tone;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className={`inline-notice ${tone}`} role={tone === "danger" ? "alert" : "note"}>
      <strong>{title}</strong>
      <div>{children}</div>
    </div>
  );
}
