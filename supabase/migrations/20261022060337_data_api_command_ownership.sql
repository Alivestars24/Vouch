-- FastAPI owns commands and the worker owns execution. A tenant role alone is
-- insufficient to validate approval versions, upload rights, budgets or leases.
-- The public prototype remains readable through tenant-scoped SELECT policies;
-- authenticated Data API requests cannot mutate application state directly.
do $command_ownership$
declare
  table_name text;
  policy_name text;
  application_tables text[] := array[
    'organizations', 'memberships', 'membership_roles', 'brands', 'products',
    'product_versions', 'creators', 'creator_evidence', 'rule_packs',
    'rule_pack_versions', 'rules', 'campaigns', 'campaign_rule_pins',
    'campaign_creators', 'consent_receipts', 'upload_intents', 'media_assets',
    'submissions', 'submission_versions', 'analyses', 'evidence_items',
    'findings', 'finding_evidence', 'finding_decisions', 'review_contexts',
    'review_events', 'approvals', 'jobs', 'job_stages', 'idempotency_records',
    'budget_accounts', 'budget_reservations', 'usage_ledger',
    'provider_artifacts', 'deletion_requests', 'deletion_items',
    'deletion_tombstones', 'audit_events'
  ];
begin
  foreach table_name in array application_tables loop
    execute format('revoke all on table public.%I from anon, authenticated', table_name);
    execute format('grant select on table public.%I to authenticated', table_name);

    for policy_name in
      select policyname
      from pg_policies
      where schemaname = 'public'
        and tablename = table_name
        and cmd <> 'SELECT'
    loop
      execute format('drop policy %I on public.%I', policy_name, table_name);
    end loop;
  end loop;
end
$command_ownership$;
