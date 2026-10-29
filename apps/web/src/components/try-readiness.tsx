import Link from "next/link";

import { StatusBadge } from "@/components/status";
import styles from "./try-readiness.module.css";

const readinessChecks = [
  {
    label: "Operator region",
    value: "India (IN)",
    status: "policy_restricted",
    detail: "The current Meta geographic policy blocks Muse Image access from India.",
  },
  {
    label: "Account catalog",
    value: "Muse Image listed",
    status: "configured_unverified",
    detail: "Catalog visibility is not permission to call a region-restricted model.",
  },
  {
    label: "Customer photo",
    value: "Not collected",
    status: "ready",
    detail: "Vouch stops before upload, so no face image leaves the customer device.",
  },
] as const;

export function TryReadiness() {
  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <div>
          <p className="eyebrow">Vouch Try · eligibility gate</p>
          <h1>Preview access stops before the photo.</h1>
          <p className={styles.lede}>
            This workspace operates from India. Muse Image is therefore disabled even though the
            model appears in the account catalog.
          </p>
        </div>
        <StatusBadge value="policy_restricted" label="Blocked for India" />
      </header>

      <section className={styles.decision} aria-labelledby="try-decision-heading">
        <div className={styles.decisionMark} aria-hidden="true">03</div>
        <div>
          <p className="eyebrow">Current decision</p>
          <h2 id="try-decision-heading">Do not upload or call Muse Image</h2>
          <p>
            A key, account access, or an overseas deployment does not override the operator-region
            gate. Vouch will not route around it or send the photo to another provider.
          </p>
        </div>
      </section>

      <section className={styles.checks} aria-labelledby="try-checks-heading">
        <div className={styles.sectionHeading}>
          <div>
            <p className="eyebrow">Decision evidence</p>
            <h2 id="try-checks-heading">Why the control is locked</h2>
          </div>
          <span className={styles.checkedAt}>Checked 27 Oct 2026</span>
        </div>
        <dl>
          {readinessChecks.map((check) => (
            <div key={check.label}>
              <dt>{check.label}</dt>
              <dd>
                <strong>{check.value}</strong>
                <StatusBadge value={check.status} />
              </dd>
              <p>{check.detail}</p>
            </div>
          ))}
        </dl>
      </section>

      <aside className={styles.next} aria-labelledby="try-next-heading">
        <div>
          <p className="eyebrow">Available now</p>
          <h2 id="try-next-heading">Keep the campaign moving without a risky workaround.</h2>
          <p>Use authorized creator evidence in Find, then review the exact draft in Check.</p>
        </div>
        <div className={styles.actions}>
          <Link className="button primary" href="/find">Open Find</Link>
          <Link className="button secondary" href="/#campaigns">Open campaigns</Link>
        </div>
      </aside>
    </div>
  );
}
