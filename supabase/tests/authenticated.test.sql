-- Transactional synthetic data: never provisions Auth accounts or persists test objects.
begin;
select no_plan();
-- Local migration owner may create roles but does not inherit SET ROLE automatically.
-- This membership is transaction-local test preparation and is rolled back below.
grant vouch_api, vouch_worker, vouch_retention to postgres;
grant usage on schema extensions to vouch_api, vouch_worker, vouch_retention;
create function pg_temp.vouch_test_id(name text) returns uuid language sql immutable as $$
  select md5('vouch.authenticated.test.' || name)::uuid
$$;

insert into vouch.organizations
  (id, slug, name, budget_cap_minor, budget_held_minor, budget_settled_minor, budget_currency)
select pg_temp.vouch_test_id('org-' || suffix), 'auth-policy-test-' || suffix,
  'Policy test ' || suffix, 1000, 0, 0, 'USD' from (values ('a'),('b')) v(suffix);
insert into vouch.users (id, email, display_name, auth_subject)
select pg_temp.vouch_test_id('user-' || name), name || '@policy.vouch.test', name,
  pg_temp.vouch_test_id('auth-' || name)
from (values ('admin'),('reviewer'),('viewer'),('beta'),('revoked')) v(name);
insert into vouch.memberships (id, organization_id, user_id, active)
select pg_temp.vouch_test_id('membership-' || name),
  pg_temp.vouch_test_id(case when name = 'beta' then 'org-b' else 'org-a' end),
  pg_temp.vouch_test_id('user-' || name), name <> 'revoked'
from (values ('admin'),('reviewer'),('viewer'),('beta'),('revoked')) v(name);
insert into vouch.membership_roles (id, organization_id, membership_id, role)
select pg_temp.vouch_test_id('role-' || name || '-' || role),
  pg_temp.vouch_test_id(case when name = 'beta' then 'org-b' else 'org-a' end),
  pg_temp.vouch_test_id('membership-' || name), role
from (values ('admin','admin'),('admin','marketer'),('reviewer','reviewer'),
  ('viewer','viewer'),('beta','admin'),('revoked','admin')) v(name, role);
insert into vouch.brands (id, organization_id, name)
select pg_temp.vouch_test_id('brand-' || suffix), pg_temp.vouch_test_id('org-' || suffix),
  'Policy brand' from (values ('a'),('b')) v(suffix);
insert into vouch.products (id, organization_id, brand_id, name, category, sku, version)
select pg_temp.vouch_test_id('product-' || suffix), pg_temp.vouch_test_id('org-' || suffix),
  pg_temp.vouch_test_id('brand-' || suffix), 'Policy product', 'fixture', suffix, 1
from (values ('a'),('b')) v(suffix);
insert into vouch.creators (id, organization_id, name, handle, rights_status, evidence_timestamp)
select pg_temp.vouch_test_id('creator-' || suffix), pg_temp.vouch_test_id('org-' || suffix),
  'Policy creator', suffix, 'permission_recorded', now() from (values ('a'),('b')) v(suffix);
insert into vouch.rule_pack_versions
  (id, organization_id, name, version, status, source_uri, content_hash, rules)
select pg_temp.vouch_test_id('rules-' || suffix), pg_temp.vouch_test_id('org-' || suffix),
  'Policy pack', '1', 'reviewed', 'fixture://policy', repeat('a',64), '[]'
from (values ('a'),('b')) v(suffix);
insert into vouch.campaigns
  (id, organization_id, name, objective, market, product_id, rule_pack_version_id, created_by, created_at)
select pg_temp.vouch_test_id('campaign-' || suffix), pg_temp.vouch_test_id('org-' || suffix),
  'Policy campaign', 'Synthetic', 'IN', pg_temp.vouch_test_id('product-' || suffix),
  pg_temp.vouch_test_id('rules-' || suffix),
  pg_temp.vouch_test_id(case when suffix = 'b' then 'user-beta' else 'user-admin' end), now()
from (values ('a'),('b')) v(suffix);
insert into vouch.media_assets (id, organization_id, campaign_id, uploader_user_id,
  filename, proposed_content_type, expected_bytes, status, upload_token_hash,
  finalize_token_hash, rights_attested, retention_deadline, created_at, storage_backend, object_key)
select pg_temp.vouch_test_id('asset-' || suffix), pg_temp.vouch_test_id('org-' || suffix),
  pg_temp.vouch_test_id('campaign-' || suffix),
  pg_temp.vouch_test_id(case when suffix = 'b' then 'user-beta' else 'user-admin' end),
  'fixture.mp4', 'video/mp4', 32, 'intent_created', repeat('a',64), repeat('b',64),
  true, now() + interval '1 day', now(), 'supabase',
  pg_temp.vouch_test_id('org-' || suffix)::text || '/' ||
  pg_temp.vouch_test_id('campaign-' || suffix)::text || '/' ||
  pg_temp.vouch_test_id('asset-' || suffix)::text || '/source'
from (values ('a'),('b')) v(suffix);
insert into vouch.submissions (id, organization_id, campaign_id, creator_id, created_at)
select pg_temp.vouch_test_id('submission-' || suffix), pg_temp.vouch_test_id('org-' || suffix),
  pg_temp.vouch_test_id('campaign-' || suffix), pg_temp.vouch_test_id('creator-' || suffix), now()
from (values ('a'),('b')) v(suffix);
insert into vouch.submission_versions (id, organization_id, submission_id, version_no, asset_id,
  media_hash, caption, caption_hash, uploader_user_id, rights_attested, created_at)
select pg_temp.vouch_test_id('version-' || suffix), pg_temp.vouch_test_id('org-' || suffix),
  pg_temp.vouch_test_id('submission-' || suffix), 1, pg_temp.vouch_test_id('asset-' || suffix),
  repeat('c',64), 'Synthetic caption', repeat('d',64),
  pg_temp.vouch_test_id(case when suffix = 'b' then 'user-beta' else 'user-admin' end), true, now()
from (values ('a'),('b')) v(suffix);
update vouch.submissions set current_version_id = pg_temp.vouch_test_id(
  case when id = pg_temp.vouch_test_id('submission-a') then 'version-a' else 'version-b' end)
where id in (pg_temp.vouch_test_id('submission-a'), pg_temp.vouch_test_id('submission-b'));
insert into vouch.analyses (id, organization_id, submission_version_id, analysis_status,
  machine_assessment, manifest_hash, invocation_mode, scenario, required_coverage,
  observed_coverage, missing_intervals, model_versions, prompt_version, schema_version, created_at)
select pg_temp.vouch_test_id('analysis-' || suffix), pg_temp.vouch_test_id('org-' || suffix),
  pg_temp.vouch_test_id('version-' || suffix),
  case when suffix = 'a' then 'completed' else 'queued' end,
  'not_assessed', repeat('e',64),
  'fixture', 'clean', '["speech","visual"]', '[]', '[]', '{}', 'fixture-v1', '1', now()
from (values ('a'),('b')) v(suffix);
insert into vouch.jobs (id, organization_id, kind, resource_id, logical_key, status,
  attempt_count, max_attempts, fence, scenario, created_at, updated_at)
select pg_temp.vouch_test_id('job-' || suffix), pg_temp.vouch_test_id('org-' || suffix),
  'check', pg_temp.vouch_test_id('analysis-' || suffix), 'policy-test-' || suffix,
  'queued', 0, 3, 0, 'clean', now(), now() from (values ('a'),('b')) v(suffix);
insert into vouch.evidence_items (id, organization_id, analysis_id, modality, precision, description, captured_at)
values (pg_temp.vouch_test_id('evidence-a'), pg_temp.vouch_test_id('org-a'),
  pg_temp.vouch_test_id('analysis-a'), 'speech', 'fixture', 'Synthetic evidence', now());
insert into vouch.review_contexts (id, organization_id, analysis_id, submission_id,
  submission_version_id, review_status, revision, manifest_hash)
values (pg_temp.vouch_test_id('review-a'), pg_temp.vouch_test_id('org-a'),
  pg_temp.vouch_test_id('analysis-a'), pg_temp.vouch_test_id('submission-a'),
  pg_temp.vouch_test_id('version-a'), 'unreviewed', 1, repeat('e',64));
insert into vouch.fix_request_drafts
  (id, organization_id, analysis_id, text, created_by, created_at)
values (
  pg_temp.vouch_test_id('feedback-draft-a'), pg_temp.vouch_test_id('org-a'),
  pg_temp.vouch_test_id('analysis-a'), 'Internal draft selected for explicit sharing',
  pg_temp.vouch_test_id('user-admin'), now()
);
-- Publication requires a finalized active source. Restore the upload-intent fixture
-- before the later browser Storage policy assertions.
update vouch.media_assets
set status = 'validated', validated_content_type = 'video/mp4', actual_bytes = 32,
  sha256 = repeat('c', 64), duration_ms = 10000
where id = pg_temp.vouch_test_id('asset-a');
insert into vouch.consent_receipts (
  id, organization_id, asset_id, campaign_id, actor_user_id, purpose,
  notice_version, notice_hash, accepted_at
) values (
  pg_temp.vouch_test_id('feedback-consent-a'), pg_temp.vouch_test_id('org-a'),
  pg_temp.vouch_test_id('asset-a'), pg_temp.vouch_test_id('campaign-a'),
  pg_temp.vouch_test_id('user-admin'), 'campaign_check',
  'feedback-policy-notice-v1', repeat('9',64), now()
);

select ok((select bool_and(not rolsuper and not rolbypassrls and not rolcanlogin and not rolcreaterole)
  from pg_roles where rolname in ('vouch_api','vouch_worker')), 'runtime group roles are restricted');
select has_column('vouch','users','auth_subject','domain users have verified-subject mapping');
select has_column('vouch','media_assets','object_key','private media has domain-owned object key');
select ok((select not public and file_size_limit = 5000000
  and allowed_mime_types = array['video/mp4','video/webm'] from storage.buckets
  where id = 'vouch-media'), 'bucket is private with exact API limits');
select ok(not has_table_privilege('vouch_api','vouch.users','UPDATE'), 'API cannot change subject mappings');
select ok(not has_table_privilege('vouch_api','vouch.memberships','INSERT,UPDATE,DELETE'), 'API cannot grant membership');
select ok(not has_table_privilege('vouch_api','vouch.membership_roles','INSERT,UPDATE,DELETE'), 'API cannot grant roles');
select ok(not has_table_privilege('vouch_api','vouch.rule_pack_versions','INSERT,UPDATE,DELETE'), 'API cannot change pinned rulebooks');
select ok(not has_table_privilege('vouch_worker','vouch.approvals','INSERT,UPDATE,DELETE'), 'worker cannot approve');
select ok(not has_table_privilege('vouch_worker','vouch.finding_decisions','INSERT,UPDATE,DELETE'), 'worker cannot make human finding decisions');
select ok(not has_table_privilege('vouch_api','vouch.evidence_items','INSERT'), 'API cannot publish machine evidence');
select ok(not has_table_privilege('vouch_api','vouch.findings','INSERT'), 'API cannot publish machine findings');
select ok(
  has_table_privilege('vouch_api','vouch.creator_feedback','SELECT,INSERT')
  and has_column_privilege('vouch_api','vouch.creator_feedback','message','UPDATE')
  and has_column_privilege('vouch_api','vouch.creator_feedback','start_ms','UPDATE')
  and has_column_privilege('vouch_api','vouch.creator_feedback','end_ms','UPDATE')
  and not has_column_privilege('vouch_api','vouch.creator_feedback','manifest_hash','UPDATE')
  and not has_table_privilege('vouch_api','vouch.creator_feedback','DELETE'),
  'API may publish immutable feedback and scrub only creator-visible snapshot fields'
);
select ok(
  (select bool_and(not has_table_privilege(
    data_role, 'vouch.creator_feedback', 'SELECT,INSERT,UPDATE,DELETE'
  )) from (values ('anon'), ('authenticated'), ('vouch_worker'), ('vouch_guest')) roles(data_role)),
  'browser, worker and guest roles have no direct feedback table access'
);

set local role vouch_api;
select is((select count(*)::integer from vouch.campaigns), 0, 'missing request context sees no tenant campaigns');
select is((select count(*)::integer from vouch.users), 0, 'missing subject sees no identities');
select set_config('vouch.auth_subject', pg_temp.vouch_test_id('auth-admin')::text, true);
select is((select count(*)::integer from vouch.users), 1, 'verified subject bootstraps only its own user');
select is((select count(*)::integer from vouch.memberships), 1, 'bootstrap reads own active memberships only');
select is((select count(*)::integer from vouch.organizations), 1, 'bootstrap lists only joined organizations');
select is((select count(*)::integer from vouch.membership_roles), 2, 'bootstrap role reads come from stored membership');
select is((select count(*)::integer from vouch.campaigns), 0, 'subject without selected organization sees no domain data');
select set_config('vouch.user_id', pg_temp.vouch_test_id('user-admin')::text, true);
select set_config('vouch.organization_id', pg_temp.vouch_test_id('org-a')::text, true);
select is((select count(*)::integer from vouch.campaigns), 1, 'verified member sees selected organization');
select is((select count(*)::integer from vouch.campaigns
  where organization_id = pg_temp.vouch_test_id('org-b')), 0, 'missing caller filter cannot expose cross-tenant rows');
select lives_ok($$insert into vouch.creator_feedback (
  id, organization_id, submission_id, submission_version_id, analysis_id,
  fix_request_draft_id, message, start_ms, end_ms, invocation_mode,
  analysis_status, manifest_hash, published_by_user_id, idempotency_key,
  request_digest, published_at
) values (
  pg_temp.vouch_test_id('feedback-admin'), pg_temp.vouch_test_id('org-a'),
  pg_temp.vouch_test_id('submission-a'), pg_temp.vouch_test_id('version-a'),
  pg_temp.vouch_test_id('analysis-a'), pg_temp.vouch_test_id('feedback-draft-a'),
  'Trim the unsupported claim before resubmitting.', 1000, 2000, 'fixture',
  'completed', repeat('e',64), pg_temp.vouch_test_id('user-admin'),
  'feedback-admin-key', repeat('f',64), now()
)$$, 'admin may explicitly publish an exact allowlisted feedback snapshot');
select is(
  (select count(*)::integer from vouch.creator_feedback), 1,
  'authorized API read sees only selected-tenant published feedback'
);
select throws_ok($$insert into vouch.creator_feedback (
  id, organization_id, submission_id, submission_version_id, analysis_id,
  fix_request_draft_id, message, start_ms, end_ms, invocation_mode,
  analysis_status, manifest_hash, published_by_user_id, idempotency_key,
  request_digest, published_at
) values (
  pg_temp.vouch_test_id('feedback-admin-replay'), pg_temp.vouch_test_id('org-a'),
  pg_temp.vouch_test_id('submission-a'), pg_temp.vouch_test_id('version-a'),
  pg_temp.vouch_test_id('analysis-a'), pg_temp.vouch_test_id('feedback-draft-a'),
  'Conflicting replay body.', null, null, 'fixture', 'completed', repeat('e',64),
  pg_temp.vouch_test_id('user-admin'), 'feedback-admin-key', repeat('1',64), now()
)$$, '23505', null, 'feedback idempotency key is unique within tenant and publishing actor');
select throws_ok($$insert into vouch.creator_feedback (
  id, organization_id, submission_id, submission_version_id, analysis_id,
  fix_request_draft_id, message, start_ms, end_ms, invocation_mode,
  analysis_status, manifest_hash, published_by_user_id, idempotency_key,
  request_digest, published_at
) values (
  pg_temp.vouch_test_id('feedback-forged-provenance'), pg_temp.vouch_test_id('org-a'),
  pg_temp.vouch_test_id('submission-a'), pg_temp.vouch_test_id('version-a'),
  pg_temp.vouch_test_id('analysis-a'), pg_temp.vouch_test_id('feedback-draft-a'),
  'Forged live provenance.', null, null, 'live', 'completed', repeat('e',64),
  pg_temp.vouch_test_id('user-admin'), 'feedback-forged-key', repeat('2',64), now()
)$$, '23514', null, 'publication cannot forge analysis invocation provenance');
reset role;
update vouch.analyses set analysis_status = 'queued'
where id = pg_temp.vouch_test_id('analysis-a');
set local role vouch_api;
select set_config('vouch.auth_subject', pg_temp.vouch_test_id('auth-admin')::text, true);
select set_config('vouch.user_id', pg_temp.vouch_test_id('user-admin')::text, true);
select set_config('vouch.organization_id', pg_temp.vouch_test_id('org-a')::text, true);
select throws_ok($$update vouch.users set auth_subject = null$$, '42501', null, 'runtime subject mutation denied');
select throws_ok($$update vouch.memberships set active = true$$, '42501', null, 'runtime membership mutation denied');
select throws_ok($$insert into vouch.approvals default values$$, '42501', null, 'marketer cannot insert human approval');
select throws_ok($$insert into vouch.evidence_items default values$$, '42501', null, 'API cannot forge evidence');
select throws_ok($$update vouch.analyses set analysis_status = 'completed', machine_assessment = 'no_issues_detected'
  where id = pg_temp.vouch_test_id('analysis-a')$$, '42501', null, 'API cannot publish completed machine assessment');
select throws_ok($$update vouch.evidence_items set description = 'forged'
  where id = pg_temp.vouch_test_id('evidence-a')$$, '42501', null, 'API cannot rewrite evidence descriptions');
select lives_ok($$update vouch.analyses set job_id = pg_temp.vouch_test_id('job-a')
  where id = pg_temp.vouch_test_id('analysis-a')$$, 'API can link queued analysis to its job');
select lives_ok($$update vouch.review_contexts set review_status = 'superseded', revision = 2,
  superseded_at = now() where id = pg_temp.vouch_test_id('review-a')$$,
  'marketer may supersede an earlier review during revision');
select lives_ok($$insert into vouch.review_events (id,organization_id,review_context_id,
  action,rationale,actor_user_id,review_revision,manifest_hash,created_at)
  values (pg_temp.vouch_test_id('supersede-event'),pg_temp.vouch_test_id('org-a'),
    pg_temp.vouch_test_id('review-a'),'superseded','Synthetic revision',
    pg_temp.vouch_test_id('user-admin'),2,repeat('e',64),now())$$,
  'marketer may record only exact-context supersession event');
select throws_ok($$insert into vouch.review_events (id,organization_id,review_context_id,
  action,rationale,actor_user_id,review_revision,manifest_hash,created_at)
  values (pg_temp.vouch_test_id('forged-human-event'),pg_temp.vouch_test_id('org-a'),
    pg_temp.vouch_test_id('review-a'),'approve','Forged human action',
    pg_temp.vouch_test_id('user-admin'),2,repeat('e',64),now())$$,
  '42501', null, 'supersession exception does not grant marketer human approval event');
select throws_ok($$insert into vouch.review_events (id,organization_id,review_context_id,
  action,rationale,actor_user_id,review_revision,manifest_hash,created_at)
  values (pg_temp.vouch_test_id('stale-supersede-event'),pg_temp.vouch_test_id('org-a'),
    pg_temp.vouch_test_id('review-a'),'superseded','Stale context',
    pg_temp.vouch_test_id('user-admin'),1,repeat('e',64),now())$$,
  '42501', null, 'marketer cannot record stale-version supersession event');
select set_config('vouch.organization_id', pg_temp.vouch_test_id('org-b')::text, true);
select is((select count(*)::integer from vouch.campaigns), 0, 'selecting another organization does not grant membership');
select set_config('vouch.organization_id', pg_temp.vouch_test_id('org-a')::text, true);
select set_config('vouch.user_id', pg_temp.vouch_test_id('user-reviewer')::text, true);
select is((select count(*)::integer from vouch.campaigns), 0, 'subject and domain user must agree');
select set_config('vouch.auth_subject', pg_temp.vouch_test_id('auth-revoked')::text, true);
select set_config('vouch.user_id', pg_temp.vouch_test_id('user-revoked')::text, true);
select is((select count(*)::integer from vouch.memberships), 0, 'revoked membership excluded from workspace bootstrap');
select is((select count(*)::integer from vouch.campaigns), 0, 'revoked member denied despite stored admin role');

-- Restore the synthetic context as the migration owner so reviewer publication
-- is proved independently from the preceding supersession policy assertions.
reset role;
update vouch.review_contexts
set review_status = 'unreviewed', revision = 1, superseded_at = null
where id = pg_temp.vouch_test_id('review-a');
update vouch.analyses set analysis_status = 'completed'
where id = pg_temp.vouch_test_id('analysis-a');
set local role vouch_api;
select set_config('vouch.auth_subject', pg_temp.vouch_test_id('auth-reviewer')::text, true);
select set_config('vouch.user_id', pg_temp.vouch_test_id('user-reviewer')::text, true);
select is((select count(*)::integer from vouch.creator_feedback), 1,
  'reviewer may read explicitly published feedback in the selected tenant');
select lives_ok($$insert into vouch.creator_feedback (
  id, organization_id, submission_id, submission_version_id, analysis_id,
  fix_request_draft_id, message, start_ms, end_ms, invocation_mode,
  analysis_status, manifest_hash, published_by_user_id, idempotency_key,
  request_digest, published_at
) values (
  pg_temp.vouch_test_id('feedback-reviewer'), pg_temp.vouch_test_id('org-a'),
  pg_temp.vouch_test_id('submission-a'), pg_temp.vouch_test_id('version-a'),
  pg_temp.vouch_test_id('analysis-a'), pg_temp.vouch_test_id('feedback-draft-a'),
  'Reviewer-approved wording for the creator.', null, null, 'fixture', 'completed',
  repeat('e',64), pg_temp.vouch_test_id('user-reviewer'), 'feedback-reviewer-key',
  repeat('3',64), now()
)$$, 'reviewer can publish a separately approved snapshot without owning the draft');
select is((select count(*)::integer from vouch.submissions
  where id = pg_temp.vouch_test_id('submission-a') and deleted_at is null),
  1, 'reviewer sees valid undeleted source before taking lock');
select is((select count(*)::integer from (select id from vouch.submissions
  where id = pg_temp.vouch_test_id('submission-a') for update) locked),
  1, 'reviewer can take same-tenant approval/deletion serialization lock');
select throws_ok($$update vouch.submissions set current_version_id = null
  where id = pg_temp.vouch_test_id('submission-a')$$, '42501', null,
  'reviewer lock permission cannot change current content pointer');
select throws_ok($$update vouch.submissions set deleted_at = now()
  where id = pg_temp.vouch_test_id('submission-a')$$, '42501', null,
  'reviewer lock permission cannot delete source');
select set_config('vouch.auth_subject', pg_temp.vouch_test_id('auth-viewer')::text, true);
select set_config('vouch.user_id', pg_temp.vouch_test_id('user-viewer')::text, true);
select is((select count(*)::integer from vouch.creator_feedback), 0,
  'viewer cannot read creator feedback publication records');
select throws_ok($$insert into vouch.creator_feedback (
  id, organization_id, submission_id, submission_version_id, analysis_id,
  fix_request_draft_id, message, invocation_mode, analysis_status, manifest_hash,
  published_by_user_id, idempotency_key, request_digest, published_at
) values (
  pg_temp.vouch_test_id('feedback-viewer'), pg_temp.vouch_test_id('org-a'),
  pg_temp.vouch_test_id('submission-a'), pg_temp.vouch_test_id('version-a'),
  pg_temp.vouch_test_id('analysis-a'), pg_temp.vouch_test_id('feedback-draft-a'),
  'Viewer must not publish.', 'fixture', 'completed', repeat('e',64),
  pg_temp.vouch_test_id('user-viewer'), 'feedback-viewer-key', repeat('4',64), now()
)$$, '42501', null, 'viewer cannot publish feedback despite holding the restricted API role');
select is((select count(*)::integer from (select id from vouch.submissions
  where id = pg_temp.vouch_test_id('submission-a') for update) locked),
  1, 'viewer read can take same-tenant source-availability lock');
select throws_ok($$update vouch.submissions set current_version_id = null
  where id = pg_temp.vouch_test_id('submission-a')$$, '42501', null,
  'viewer lock permission cannot change current content pointer');
select throws_ok($$update vouch.submissions set deleted_at = now()
  where id = pg_temp.vouch_test_id('submission-a')$$, '42501', null,
  'viewer lock permission cannot delete source');
select is((select count(*)::integer from (select id from vouch.submissions
  where id = pg_temp.vouch_test_id('submission-b') for update) locked),
  0, 'lock permission does not expose another tenant');

reset role;
update vouch.analyses set analysis_status = 'queued'
where id = pg_temp.vouch_test_id('analysis-a');
select set_config('vouch.organization_id', '', true);
set local role vouch_worker;
select ok((select count(*) >= 2 from vouch.jobs), 'worker can discover jobs across tenants');
select is((select count(*)::integer from vouch.analyses), 0, 'worker source/result queries need derived tenant context');
select set_config('vouch.organization_id', pg_temp.vouch_test_id('org-a')::text, true);
select is((select count(*)::integer from vouch.analyses), 1, 'worker sees only derived organization analysis');
select lives_ok($$select id from vouch.submissions
  where id = pg_temp.vouch_test_id('submission-a') for update$$, 'worker can take publication/deletion serialization lock');
select throws_ok($$update vouch.submissions set current_version_id = null
  where id = pg_temp.vouch_test_id('submission-a')$$, '42501', null, 'worker cannot change current content pointer');
select throws_ok($$insert into vouch.approvals default values$$, '42501', null, 'worker approval write denied by grants');
select throws_ok($$update vouch.review_contexts set review_status = 'approved'$$, '42501', null, 'worker human approval transition denied');
select lives_ok($$insert into vouch.evidence_items
  (id,organization_id,analysis_id,modality,precision,description,captured_at)
  values (pg_temp.vouch_test_id('worker-evidence'),pg_temp.vouch_test_id('org-a'),
    pg_temp.vouch_test_id('analysis-a'),'visual','fixture','Worker evidence',now())$$,
  'worker can publish in derived tenant');
select throws_ok($$insert into vouch.evidence_items
  (id,organization_id,analysis_id,modality,precision,description,captured_at)
  values (pg_temp.vouch_test_id('worker-cross-evidence'),pg_temp.vouch_test_id('org-b'),
    pg_temp.vouch_test_id('analysis-b'),'visual','fixture','Cross evidence',now())$$,
  '42501', null, 'worker cannot publish outside derived tenant');

reset role;
update vouch.media_assets
set status = 'intent_created', validated_content_type = null, actual_bytes = null, sha256 = null
where id = pg_temp.vouch_test_id('asset-a');
select set_config('request.jwt.claim.sub', pg_temp.vouch_test_id('auth-admin')::text, true);
select set_config('request.jwt.claims', json_build_object('sub',pg_temp.vouch_test_id('auth-admin'),'role','authenticated')::text, true);
set local role authenticated;
select throws_ok($$select * from vouch.media_assets$$, '42501', null, 'browser cannot read private domain tables');
select lives_ok($$insert into storage.objects (bucket_id,name)
  values ('vouch-media',pg_temp.vouch_test_id('org-a')::text || '/' ||
    pg_temp.vouch_test_id('campaign-a')::text || '/' || pg_temp.vouch_test_id('asset-a')::text || '/source')$$,
  'current uploader may create exact fresh authorized object');
select is((select count(*)::integer from storage.objects where bucket_id = 'vouch-media'),
  1, 'uploader can reconcile fresh pending bytes');
select throws_ok($$insert into storage.objects (bucket_id,name)
  values ('vouch-media',pg_temp.vouch_test_id('org-b')::text || '/' ||
    pg_temp.vouch_test_id('campaign-b')::text || '/' || pg_temp.vouch_test_id('asset-b')::text || '/source')$$,
  '42501', null, 'cross-tenant Storage insert denied');
select throws_ok($$insert into storage.objects (bucket_id,name) values ('vouch-media','arbitrary/key')$$,
  '42501', null, 'caller-selected arbitrary Storage key denied');
with changed as (update storage.objects set name = 'replaced'
  where bucket_id = 'vouch-media' returning id)
select is((select count(*)::integer from changed),
  0, 'client cannot overwrite private media');
-- Emulate Storage API's deletion transaction flag; exercise RLS rather than its
-- separate protective trigger. These are rollback-only metadata, not stored files.
select set_config('storage.allow_delete_query', 'true', true);
with removed as (delete from storage.objects where bucket_id = 'vouch-media' returning id)
select is((select count(*)::integer from removed), 0, 'client cannot bypass deletion receipts');

reset role;
update vouch.media_assets set created_at = now() - interval '6 minutes'
  where id = pg_temp.vouch_test_id('asset-a');
set local role authenticated;
select is((select count(*)::integer from storage.objects where bucket_id = 'vouch-media'),
  0, 'expired pending upload cannot be reconciled or finalized through Storage');
reset role;
update vouch.media_assets set created_at = now(), rights_attested = false
  where id = pg_temp.vouch_test_id('asset-a');
set local role authenticated;
select is((select count(*)::integer from storage.objects where bucket_id = 'vouch-media'),
  0, 'missing rights attestation denies Storage reads');
reset role;
update vouch.media_assets set rights_attested = true where id = pg_temp.vouch_test_id('asset-a');
update vouch.memberships set active = false where id = pg_temp.vouch_test_id('membership-admin');
set local role authenticated;
select is((select count(*)::integer from storage.objects where bucket_id = 'vouch-media'),
  0, 'Storage rechecks current membership, not stale JWT role claims');
reset role;
update vouch.memberships set active = true where id = pg_temp.vouch_test_id('membership-admin');

reset role;
select set_config('request.jwt.claim.sub', pg_temp.vouch_test_id('auth-viewer')::text, true);
select set_config('request.jwt.claims', json_build_object('sub',pg_temp.vouch_test_id('auth-viewer'),'role','authenticated')::text, true);
set local role authenticated;
select is((select count(*)::integer from storage.objects where bucket_id = 'vouch-media'),
  0, 'viewer cannot read another uploader pending content');
reset role;
update vouch.media_assets set status = 'validated' where id = pg_temp.vouch_test_id('asset-a');
set local role authenticated;
select is((select count(*)::integer from storage.objects where bucket_id = 'vouch-media'),
  1, 'viewer may read validated private asset in its organization');
reset role;
update vouch.media_assets set deleted_at = now(), status = 'deleted'
  where id = pg_temp.vouch_test_id('asset-a');
set local role authenticated;
select is((select count(*)::integer from storage.objects where bucket_id = 'vouch-media'),
  0, 'tombstoned media cannot be downloaded before remote cleanup');
reset role;
select set_config('request.jwt.claim.sub', pg_temp.vouch_test_id('auth-beta')::text, true);
select set_config('request.jwt.claims', json_build_object('sub',pg_temp.vouch_test_id('auth-beta'),'role','authenticated')::text, true);
set local role authenticated;
select is((select count(*)::integer from storage.objects where bucket_id = 'vouch-media'),
  0, 'other-tenant bearer cannot read private object');
reset role;
select set_config('request.jwt.claim.sub', '', true);
select set_config('request.jwt.claims', '{}', true);
set local role anon;
select is((select count(*)::integer from storage.objects where bucket_id = 'vouch-media'),
  0, 'anonymous private Storage read denied');
select throws_ok($$insert into storage.objects (bucket_id,name) values ('vouch-media','anonymous')$$,
  '42501', null, 'anonymous private Storage write denied');

reset role;
select set_config('vouch.auth_subject', pg_temp.vouch_test_id('auth-admin')::text, true);
select set_config('vouch.user_id', pg_temp.vouch_test_id('user-admin')::text, true);
select set_config('vouch.organization_id', pg_temp.vouch_test_id('org-a')::text, true);
set local role vouch_api;
select lives_ok($$update vouch.creator_feedback
  set message = '', start_ms = null, end_ms = null
  where submission_id = pg_temp.vouch_test_id('submission-a')$$,
  'API erases only creator-visible feedback fields after exact source deletion');
select is((select count(*)::integer from vouch.creator_feedback
  where message = '' and start_ms is null and end_ms is null), 2,
  'feedback identifiers and immutable provenance survive member erasure');
select lives_ok($$update vouch.evidence_items set description = ''
  where id = pg_temp.vouch_test_id('evidence-a')$$, 'API can erase evidence after source deletion');
select lives_ok($$update vouch.analyses set analysis_status = 'cancelled',
  machine_assessment = 'not_assessed', observed_coverage = '[]', missing_intervals = '[]',
  completed_at = now() where id = pg_temp.vouch_test_id('analysis-a')$$,
  'API can cancel and scrub deleted-source analysis');

reset role;
select has_column('vouch','media_assets','processing_metadata',
  'measured media provenance has a persistent contract');
select ok(has_column_privilege('vouch_api','vouch.media_assets','processing_metadata','UPDATE'),
  'API can publish measured provenance during finalization');
select ok(not has_column_privilege('vouch_worker','vouch.media_assets','processing_metadata','UPDATE')
  and not has_column_privilege('vouch_retention','vouch.media_assets','processing_metadata','UPDATE'),
  'Check and retention workers cannot rewrite source provenance');
-- Reuse only the transaction's synthetic source; no real deleted source is restored.
update vouch.media_assets set status='validated',deleted_at=null,processing_metadata='{}',
  sha256=repeat('a',64),duration_ms=10000,validated_content_type='video/mp4',actual_bytes=32
  where id=pg_temp.vouch_test_id('asset-a');
set local role vouch_api;
select throws_ok($$update vouch.media_assets set processing_metadata='{"mode":"decoded"}'
  where id=pg_temp.vouch_test_id('asset-a')$$,'42501',null,
  'finalized measured provenance cannot be replaced');
select throws_ok($$update vouch.media_assets set sha256=repeat('b',64)
  where id=pg_temp.vouch_test_id('asset-a')$$,'42501',null,
  'finalized original media hash cannot be replaced');
select throws_ok($$update vouch.media_assets set duration_ms=250
  where id=pg_temp.vouch_test_id('asset-a')$$,'42501',null,
  'finalized source timebase cannot be changed');
select lives_ok($$update vouch.media_assets set status='deleted',filename='',object_bytes=null,
  deleted_at=now() where id=pg_temp.vouch_test_id('asset-a')$$,
  'source erasure still preserves immutable measured provenance');
reset role;
-- Container identity is registered only for a pending source in its actual tenant/asset scope.
update vouch.media_assets set status='content_uploaded',deleted_at=null
  where id=pg_temp.vouch_test_id('asset-a');
set local role vouch_api;
select lives_ok($$update vouch.media_assets set processing_container='vouch-media-'
  ||replace(organization_id::text,'-','')||'-'||replace(id::text,'-','')||'-'||repeat('a',32),
  processing_lease_until=now()+interval '1 minute'
  where id=pg_temp.vouch_test_id('asset-a')$$,
  'pending source may register its scoped bounded empty sandbox');
select throws_ok($$update vouch.media_assets set processing_container='vouch-media-'
  ||replace(pg_temp.vouch_test_id('org-b')::text,'-','')||'-'||replace(id::text,'-','')
  ||'-'||repeat('b',32) where id=pg_temp.vouch_test_id('asset-a')$$,
  '42501',null,'sandbox reference cannot name another tenant');
select throws_ok($$update vouch.media_assets set processing_lease_until=now()+interval '10 minutes'
  where id=pg_temp.vouch_test_id('asset-a')$$,
  '42501',null,'sandbox processing lease cannot become an indefinite hold');
reset role;
update vouch.media_assets set status='validated' where id=pg_temp.vouch_test_id('asset-a');
set local role vouch_api;
select throws_ok($$update vouch.media_assets set processing_container='vouch-media-'
  ||replace(organization_id::text,'-','')||'-'||replace(id::text,'-','')||'-'||repeat('c',32)
  where id=pg_temp.vouch_test_id('asset-a')$$,
  '42501',null,'finalized source cannot acquire a new sandbox run');
select ok(not has_column_privilege('vouch_retention','vouch.media_assets','processing_container','UPDATE'),
  'retention can erase registered containers but cannot replace their source reference');
reset role;
delete from vouch.consent_receipts
where id = pg_temp.vouch_test_id('feedback-consent-a');
-- Processing authorization is additive: the preceding synthetic assets have no receipt
-- until their member explicitly acknowledges a new pending upload below.
select has_table('vouch','consent_receipts','versioned processing authorization is persistent');
select ok((select relrowsecurity from pg_class where oid='vouch.consent_receipts'::regclass),
  'private authorization table also enforces row-level security');
select ok(not has_table_privilege('anon','vouch.consent_receipts','SELECT,INSERT,UPDATE,DELETE')
  and not has_table_privilege('authenticated','vouch.consent_receipts','SELECT,INSERT,UPDATE,DELETE'),
  'browser Data API roles have no direct authorization-table access');
select ok(not has_table_privilege('vouch_worker','vouch.consent_receipts','INSERT,UPDATE,DELETE')
  and not has_table_privilege('vouch_retention','vouch.consent_receipts','INSERT,DELETE'),
  'background processes cannot manufacture an acknowledgment');
select is((select count(*)::integer from vouch.consent_receipts
  where asset_id in (pg_temp.vouch_test_id('asset-a'),pg_temp.vouch_test_id('asset-b'))),0,
  'migration does not fabricate legacy receipts');
-- Only these transaction-local test sources are reopened; production/history is untouched.
update vouch.media_assets set status='intent_created',deleted_at=null,created_at=now(),
  retention_deadline=now()+interval '1 day',rights_attested=true
where id in (pg_temp.vouch_test_id('asset-a'),pg_temp.vouch_test_id('asset-b'));
delete from vouch.tombstones where resource_type='media_asset'
  and resource_id in (pg_temp.vouch_test_id('asset-a'),pg_temp.vouch_test_id('asset-b'));
insert into vouch.media_assets(id,organization_id,campaign_id,uploader_user_id,filename,
  proposed_content_type,expected_bytes,status,upload_token_hash,finalize_token_hash,
  rights_attested,retention_deadline,created_at)
select pg_temp.vouch_test_id(label),pg_temp.vouch_test_id('org-a'),pg_temp.vouch_test_id('campaign-a'),
  pg_temp.vouch_test_id('user-admin'),'synthetic.mp4','video/mp4',32,'intent_created',
  repeat('a',64),repeat('b',64),label<>'asset-no-rights',now()+interval '1 day',now()
from (values('asset-no-rights'),('asset-unattached')) v(label);
create function pg_temp.consent_insert(label text, asset_label text, tenant text default 'a',
  actor text default 'admin', selected_purpose text default 'campaign_check') returns void
language sql as $$
  insert into vouch.consent_receipts(id,organization_id,asset_id,campaign_id,actor_user_id,purpose,
    notice_version,notice_hash,accepted_at)
  values(pg_temp.vouch_test_id('consent-'||label),pg_temp.vouch_test_id('org-'||tenant),
    pg_temp.vouch_test_id(asset_label),pg_temp.vouch_test_id('campaign-'||tenant),
    pg_temp.vouch_test_id('user-'||actor),selected_purpose,'policy-notice-v1',repeat('a',64),now())
$$;
select set_config('vouch.auth_subject',pg_temp.vouch_test_id('auth-admin')::text,true);
select set_config('vouch.user_id',pg_temp.vouch_test_id('user-admin')::text,true);
select set_config('vouch.organization_id',pg_temp.vouch_test_id('org-a')::text,true);
set local role vouch_api;
select lives_ok($$select pg_temp.consent_insert('a','asset-a')$$,
  'current source member may acknowledge its pending campaign upload');
select lives_ok($$select pg_temp.consent_insert('unattached','asset-unattached')$$,
  'member may authorize a new upload before a Check exists');
select throws_ok($$select pg_temp.consent_insert('duplicate','asset-a')$$,'23505',null,
  'one immutable acknowledgment per asset');
select throws_ok($$select pg_temp.consent_insert('forged-actor','asset-a','a','reviewer')$$,'42501',null,
  'caller cannot fabricate another member acknowledgment');
select throws_ok($$select pg_temp.consent_insert('other-tenant','asset-b','b','beta')$$,'42501',null,
  'caller cannot acknowledge another tenant source');
select throws_ok($$select pg_temp.consent_insert('wrong-purpose','asset-a','a','admin','training')$$,
  '42501',null,'authorization purpose cannot silently change');
select throws_ok($$select pg_temp.consent_insert('no-rights','asset-no-rights')$$,'42501',null,
  'notice acknowledgment cannot substitute for source rights');
select throws_ok($$update vouch.consent_receipts set notice_hash=repeat('b',64)
  where id=pg_temp.vouch_test_id('consent-a')$$,'42501',null,
  'accepted notice hash is not a mutable command field');
select throws_ok($$update vouch.consent_receipts set accepted_at=now()-interval '1 day'
  where id=pg_temp.vouch_test_id('consent-a')$$,'42501',null,
  'accepted time cannot be rewritten');
with changed as(update vouch.consent_receipts set revoked_at=now(),
  revoked_by=pg_temp.vouch_test_id('user-admin'),revocation_actor_kind='member',revocation_reason='withdrawn'
  where id=pg_temp.vouch_test_id('consent-a') returning id)
select is((select count(*)::integer from changed),0,'withdrawal cannot revoke while leaving source live');
select set_config('vouch.auth_subject',pg_temp.vouch_test_id('auth-viewer')::text,true);
select set_config('vouch.user_id',pg_temp.vouch_test_id('user-viewer')::text,true);
select is((select count(*)::integer from vouch.consent_receipts
  where id=pg_temp.vouch_test_id('consent-a')),1,'active viewer can inspect notice provenance');
select throws_ok($$select pg_temp.consent_insert('viewer','asset-no-rights','a','viewer')$$,
  '42501',null,'viewer cannot issue an acknowledgment');
reset role;
select set_config('vouch.auth_subject',pg_temp.vouch_test_id('auth-beta')::text,true);
select set_config('vouch.user_id',pg_temp.vouch_test_id('user-beta')::text,true);
select set_config('vouch.organization_id',pg_temp.vouch_test_id('org-b')::text,true);
set local role vouch_api;
select lives_ok($$select pg_temp.consent_insert('b','asset-b','b','beta')$$,
  'second tenant may acknowledge only its own upload');
select is((select count(*)::integer from vouch.consent_receipts
  where id=pg_temp.vouch_test_id('consent-a')),0,'known receipt identifier does not bypass tenant scope');
reset role;
select set_config('vouch.organization_id',pg_temp.vouch_test_id('org-a')::text,true);
set local role vouch_worker;
select is((select count(*)::integer from vouch.consent_receipts),1,
  'Check worker reads only source receipts with a job lineage in its stored tenant');
select is((select count(*)::integer from vouch.consent_receipts
  where id=pg_temp.vouch_test_id('consent-unattached')),0,
  'Check worker cannot browse unrelated upload acknowledgments');
select throws_ok($$select pg_temp.consent_insert('worker','asset-a')$$,'42501',null,
  'Check worker cannot fabricate acknowledgment');
select throws_ok($$update vouch.consent_receipts set revoked_at=now()$$,'42501',null,
  'Check worker cannot revoke member authorization');
reset role;
select set_config('vouch.retention_asset_id',pg_temp.vouch_test_id('asset-a')::text,true);
set local role vouch_retention;
select is((select count(*)::integer from vouch.consent_receipts),0,
  'retention cannot inspect a live unexpired source acknowledgment');
select throws_ok($$select pg_temp.consent_insert('retention','asset-a')$$,'42501',null,
  'retention cannot fabricate acknowledgment');
reset role;
update vouch.media_assets set status='deleted',deleted_at=now(),filename='',object_bytes=null
  where id=pg_temp.vouch_test_id('asset-a');
select set_config('vouch.auth_subject',pg_temp.vouch_test_id('auth-admin')::text,true);
select set_config('vouch.user_id',pg_temp.vouch_test_id('user-admin')::text,true);
set local role vouch_api;
select lives_ok($$update vouch.consent_receipts set revoked_at=now(),
  revoked_by=pg_temp.vouch_test_id('user-admin'),revocation_actor_kind='member',revocation_reason='withdrawn'
  where id=pg_temp.vouch_test_id('consent-a')$$,
  'member withdrawal is permitted only after durable source denial');
select throws_ok($$update vouch.consent_receipts set revoked_at=null,revoked_by=null,
  revocation_actor_kind=null,revocation_reason=null where id=pg_temp.vouch_test_id('consent-a')$$,
  '42501',null,'withdrawn acknowledgment cannot be reactivated');
select throws_ok($$update vouch.consent_receipts set revocation_reason='source_deleted'
  where id=pg_temp.vouch_test_id('consent-a')$$,'42501',null,
  'first revocation reason and attribution remain immutable');
reset role;
update vouch.media_assets set status='deleted',deleted_at=now(),filename='',object_bytes=null,
  retention_deadline=now()-interval '1 day' where id=pg_temp.vouch_test_id('asset-b');
select set_config('vouch.organization_id',pg_temp.vouch_test_id('org-b')::text,true);
select set_config('vouch.retention_asset_id',pg_temp.vouch_test_id('asset-b')::text,true);
set local role vouch_retention;
select is((select count(*)::integer from vouch.consent_receipts),1,
  'retention can inspect only its exact expired deleted source acknowledgment');
select throws_ok($$update vouch.consent_receipts set revoked_at=now(),
  revoked_by=pg_temp.vouch_test_id('user-beta'),revocation_actor_kind='member',revocation_reason='source_deleted'
  where id=pg_temp.vouch_test_id('consent-b')$$,'42501',null,
  'system revocation cannot impersonate a member');
select lives_ok($$update vouch.consent_receipts set revoked_at=now(),revoked_by=null,
  revocation_actor_kind='retention',revocation_reason='expired'
  where id=pg_temp.vouch_test_id('consent-b')$$,
  'system expiry truthfully revokes without a human actor');
select lives_ok($$insert into vouch.audit_events(id,organization_id,actor_user_id,actor_kind,action,
  resource_type,resource_id,safe_metadata,created_at)
  values(pg_temp.vouch_test_id('consent-system-audit'),pg_temp.vouch_test_id('org-b'),null,'retention',
    'processing.authorization_revoked','consent_receipt',pg_temp.vouch_test_id('consent-b'),'{}',now())$$,
  'system authorization audit requires the real scoped system revocation');
select throws_ok($$insert into vouch.audit_events(id,organization_id,actor_user_id,actor_kind,action,
  resource_type,resource_id,safe_metadata,created_at)
  values(pg_temp.vouch_test_id('forged-consent-audit'),pg_temp.vouch_test_id('org-b'),null,'retention',
    'processing.authorization_acknowledged','consent_receipt',pg_temp.vouch_test_id('consent-b'),'{}',now())$$,
  '42501',null,'retention audit cannot pretend a member accepted the notice');
select set_config('vouch.organization_id',pg_temp.vouch_test_id('org-a')::text,true);
select is((select count(*)::integer from vouch.consent_receipts),0,
  'known system source anchor cannot cross tenant scope');
reset role;
select * from finish();
rollback;
