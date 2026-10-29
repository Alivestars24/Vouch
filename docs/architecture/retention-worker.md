# Anchored retention and cleanup

Date: 2026-10-22. Status: implemented and locally verified; exact checks are in implementation status.
This contract extends the [authenticated foundation](authenticated-foundation.md). Providers remain
fixtures. No hosted migration or provider deletion claim is authorized by this local slice.

## Outcome

An independent Python retention process discovers expired source assets and incomplete deletion
receipts, erases application content through the existing tenant-lineage deletion path, then retries
exact-key private Storage removal. Expiration never moves the original retention deadline. This
process cannot create findings, approve content, grant memberships or impersonate a human.

## Authority and persistence

- Add a separate non-bypass `vouch_retention` group/login, not membership in API/Check-worker roles.
  Discovery exposes only expired asset metadata and incomplete receipt metadata. Transaction-local
  organization/asset/receipt scope limits derivative reads and scrub-only writes. No source byte,
  caption, evidence or human decision may be inserted by this role.
- Reuse `deletion_requests` as the durable cleanup outbox rather than introducing a queue service.
  `requested_by` becomes nullable; `requested_by_kind` distinguishes `member` and `retention`.
  System receipts/audits have no human actor. Existing records remain member-attributed.
- Receipt lease fields are `attempt_count`, `max_attempts` (default 3), `retry_after`, `lease_owner`,
  `lease_until`, `fence` and `last_error_code`. Claims increment attempt/fence atomically; expired
  leases are reclaimable. Only the current fence can publish an outcome. `status=failed` means
  automatic retries exhausted, never that source access was restored or erasure succeeded.
- A human-authorized retry may retry a failed receipt, with a new fence/audit. It does not silently
  reset the automatic retry budget. Completed receipts are idempotent and never reopened.

## Ordering and failure behavior

1. Discover one eligible item; derive tenant scope from its stored record, never caller input.
2. For expiry, take the existing tenant lineage lock before source/submission/context/job locks.
   Recheck expiry, tombstone, scrub derivatives and fence Check jobs in one transaction. Create the
   durable receipt in that transaction, including abandoned upload intents with no submission.
3. Commit local erasure before Storage HTTP. Claim the receipt with a bounded lease, commit, then
   delete only domain-resolved keys. Absence must be confirmed by the Storage adapter.
4. Re-read under lock and publish only with the matching fence. On failure preserve destination
   status and use bounded backoff; after three automatic attempts retain a visible failed receipt.
   Restart/retry never creates a new deadline, duplicate receipt or human approval.

The existing immediate member deletion remains usable; it shares receipt claims/fences with the
background process. No database lock spans remote HTTP. Cleanup is idempotent but physical erasure
is eventually reconciled, not transactionally atomic with Storage. Backups and unverified provider
copies remain outside a completed local application receipt.

## Local operation and proof

Add explicit fixture/authenticated retention entrypoints to the development supervisor, with a
separate ignored `.env.retention` containing its restricted DB URL and server cleanup credential.
Do not put cleanup credentials in the Check worker or browser. Provisioning stays loopback-only.

Required proof: expiry with/without submission, derivative scrubbing, source denial, cancelled work
and released budgets, restart after erasure, partial Storage failure/retry, exhausted retry budget,
stale fence/concurrent claims, system audit attribution, and SQL denial of cross-tenant/nonexpired
edits and human approval. Run existing checks/browser workflow to detect regressions. Record actual
commands/results in [implementation status](../engineering/implementation-status.md).
