begin;
select plan(30);

select has_table('public', 'approvals', 'approval bindings table exists');
select has_column('public', 'approvals', 'manifest_hash', 'approvals bind the manifest hash');
select is(
  (select count(*)::integer from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind in ('r', 'p')
     and has_table_privilege('anon', c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')),
  0,
  'anonymous users have no public application table privileges'
);
select is(
  (select count(*)::integer from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind in ('r', 'p')
     and has_table_privilege('authenticated', c.oid, 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')),
  0,
  'authenticated Data API has no direct mutation privileges on any application table'
);
select is(
  (select count(*)::integer from pg_policies where schemaname = 'public' and cmd <> 'SELECT'),
  0,
  'no public mutation policy can reopen command bypasses'
);
select is(
  (select count(*)::integer from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind in ('r', 'p') and not c.relrowsecurity),
  0,
  'all public application tables retain RLS'
);

set local role authenticated;
set local "request.jwt.claim.sub" = 'aaaaaaaa-0000-4000-8000-000000000004';
select is((select count(*)::integer from public.organizations), 1,
  'viewer reads only their active organization');
select is((select count(*)::integer from public.brands
  where organization_id = '22222222-2222-4222-8222-222222222222'), 0,
  'explicit foreign tenant filter cannot expose its brands');
select is((select count(*)::integer from public.brands), 1,
  'viewer retains tenant-scoped read access');
select throws_ok(
  $$insert into public.brands (organization_id, name) values ('11111111-1111-4111-8111-111111111111', 'Denied brand')$$,
  '42501', null, 'viewer cannot insert a brand');

set local "request.jwt.claim.sub" = 'aaaaaaaa-0000-4000-8000-000000000002';
select throws_ok(
  $$insert into public.brands (organization_id, name) values ('11111111-1111-4111-8111-111111111111', 'Denied marketer brand')$$,
  '42501', null, 'marketer must create brands through the API');
select throws_ok(
  $$update public.submission_versions set caption_text = 'changed after approval'$$,
  '42501', null, 'marketer cannot mutate an immutable submitted version');
select throws_ok(
  $$update public.evidence_items set excerpt = 'fabricated evidence'$$,
  '42501', null, 'marketer cannot rewrite timestamped evidence');
select throws_ok(
  $$update public.analyses set manifest_hash = repeat('0', 64), coverage_complete = true$$,
  '42501', null, 'marketer cannot replace a manifest or fabricate complete coverage');
select throws_ok(
  $$insert into public.consent_receipts default values$$,
  '42501', null, 'marketer cannot fabricate consent outside API validation');
select throws_ok(
  $$insert into public.jobs default values$$,
  '42501', null, 'marketer cannot enqueue work outside the reservation transaction');
select throws_ok(
  $$insert into public.usage_ledger default values$$,
  '42501', null, 'marketer cannot forge usage or execution mode');
select throws_ok(
  $$insert into public.deletion_tombstones default values$$,
  '42501', null, 'marketer cannot forge deletion completion');

set local "request.jwt.claim.sub" = 'aaaaaaaa-0000-4000-8000-000000000003';
select throws_ok(
  $$insert into public.approvals (
    organization_id, review_context_id, analysis_id, submission_version_id,
    expected_review_version, decisions_revision, manifest_hash, asset_sha256,
    caption_sha256, rule_manifest_hash, prompt_version, model_manifest_hash,
    reviewer_user_id, rationale
  ) values (
    '11111111-1111-4111-8111-111111111111', gen_random_uuid(), gen_random_uuid(),
    gen_random_uuid(), 1, 0, repeat('0', 64), repeat('0', 64), repeat('0', 64),
    repeat('0', 64), 'forged', repeat('0', 64),
    'aaaaaaaa-0000-4000-8000-000000000001', 'Spoofed reviewer and unverified versions'
  )$$,
  '42501', null, 'reviewer cannot forge approval bindings or another reviewer identity');
select throws_ok(
  $$update public.approvals set manifest_hash = repeat('0', 64)$$,
  '42501', null, 'reviewer cannot rewrite a prior approval');
select throws_ok(
  $$update public.review_contexts set review_status = 'approved', review_version = 1$$,
  '42501', null, 'reviewer cannot bypass optimistic approval-version checks');
select throws_ok(
  $$insert into public.finding_decisions default values$$,
  '42501', null, 'reviewer decisions must pass the API and approval invalidation rules');

set local "request.jwt.claim.sub" = 'aaaaaaaa-0000-4000-8000-000000000001';
select is((select count(*)::integer from public.membership_roles
  where membership_id = 'aaaaaaaa-1000-4000-8000-000000000001' and role = 'reviewer'),
  0, 'admin does not implicitly possess the reviewer role');
select throws_ok(
  $$insert into public.membership_roles (organization_id, membership_id, role, granted_by)
    values ('11111111-1111-4111-8111-111111111111',
      'aaaaaaaa-1000-4000-8000-000000000001', 'reviewer',
      'aaaaaaaa-0000-4000-8000-000000000001')$$,
  '42501', null, 'admin cannot self-grant reviewer through the Data API');
select throws_ok(
  $$update public.organizations set check_media_retention_days = 365$$,
  '42501', null, 'admin must change retention through an authorized API command');

reset role;
update public.memberships set status = 'revoked', revoked_at = now()
  where id = 'aaaaaaaa-1000-4000-8000-000000000004';
set local role authenticated;
set local "request.jwt.claim.sub" = 'aaaaaaaa-0000-4000-8000-000000000004';
select is((select count(*)::integer from public.organizations), 0,
  'revoked membership loses organization access immediately');
select is((select count(*)::integer from public.brands), 0,
  'revoked membership loses tenant data access without a refreshed JWT');

set local "request.jwt.claim.sub" = 'bbbbbbbb-0000-4000-8000-000000000001';
select is((select count(*)::integer from public.organizations), 1,
  'second tenant retains its own organization access');
select is((select count(*)::integer from public.brands
  where organization_id = '11111111-1111-4111-8111-111111111111'), 0,
  'second tenant cannot read the first tenant');

set local role anon;
select throws_ok($$select * from public.brands$$, '42501', null,
  'anonymous Data API cannot read tenant brands');

select * from finish();
rollback;
