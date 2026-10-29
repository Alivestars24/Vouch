-- Every row and temporary role grant is rolled back. No Auth account or Storage HTTP call.
begin;
select no_plan();
grant vouch_retention to postgres;
grant usage on schema extensions to vouch_retention;
create function pg_temp.retention_id(name text) returns uuid language sql immutable as $$
  select md5('vouch.retention.test.'||name)::uuid
$$;
insert into vouch.organizations(id,slug,name,budget_cap_minor,budget_held_minor,budget_settled_minor,budget_currency)
select pg_temp.retention_id('org-'||n),'retention-test-'||n,'Retention test',1000,
  case when n='a' then 12 else 0 end,0,'USD' from (values('a'),('b')) v(n);
insert into vouch.users(id,email,display_name)
values(pg_temp.retention_id('user'),'retention-policy@vouch.test','Synthetic member');
insert into vouch.brands(id,organization_id,name)
select pg_temp.retention_id('brand-'||n),pg_temp.retention_id('org-'||n),'Synthetic'
from (values('a'),('b')) v(n);
insert into vouch.products(id,organization_id,brand_id,name,category,sku,version)
select pg_temp.retention_id('product-'||n),pg_temp.retention_id('org-'||n),
  pg_temp.retention_id('brand-'||n),'Synthetic','fixture',n,1 from (values('a'),('b')) v(n);
insert into vouch.creators(id,organization_id,name,handle,rights_status,evidence_timestamp)
select pg_temp.retention_id('creator-'||n),pg_temp.retention_id('org-'||n),
  'Synthetic',n,'permission_recorded',now() from (values('a'),('b')) v(n);
insert into vouch.rule_pack_versions(id,organization_id,name,version,status,source_uri,content_hash,rules)
select pg_temp.retention_id('rule-'||n),pg_temp.retention_id('org-'||n),
  'Synthetic','1','reviewed','fixture://retention',repeat('a',64),'[]' from (values('a'),('b')) v(n);
insert into vouch.campaigns(id,organization_id,name,objective,market,product_id,rule_pack_version_id,created_by,created_at)
select pg_temp.retention_id('campaign-'||n),pg_temp.retention_id('org-'||n),'Synthetic','Test','IN',
  pg_temp.retention_id('product-'||n),pg_temp.retention_id('rule-'||n),pg_temp.retention_id('user'),now()
from (values('a'),('b')) v(n);
insert into vouch.media_assets(id,organization_id,campaign_id,uploader_user_id,filename,
  proposed_content_type,expected_bytes,status,upload_token_hash,finalize_token_hash,object_bytes,
  rights_attested,retention_deadline,created_at)
select pg_temp.retention_id('asset-'||n),pg_temp.retention_id('org-'||tenant),
  pg_temp.retention_id('campaign-'||tenant),pg_temp.retention_id('user'),'source.mp4','video/mp4',32,
  'validated',repeat('a',64),repeat('b',64),'\x010203'::bytea,true,
  now()+case when n='c' then interval '1 day' else interval '-1 day' end,now()
from (values('a','a'),('b','b'),('c','a'),('orphan','a')) v(n,tenant);
insert into vouch.submissions(id,organization_id,campaign_id,creator_id,created_at)
select pg_temp.retention_id('submission-'||n),pg_temp.retention_id('org-'||tenant),
  pg_temp.retention_id('campaign-'||tenant),pg_temp.retention_id('creator-'||tenant),now()
from (values('a','a'),('b','b'),('c','a')) v(n,tenant);
insert into vouch.submission_versions(id,organization_id,submission_id,version_no,asset_id,
  media_hash,caption,caption_hash,uploader_user_id,rights_attested,created_at)
select pg_temp.retention_id('version-'||n),pg_temp.retention_id('org-'||tenant),
  pg_temp.retention_id('submission-'||n),1,pg_temp.retention_id('asset-'||n),repeat('a',64),
  'Source caption',repeat('b',64),pg_temp.retention_id('user'),true,now()
from (values('a','a'),('b','b'),('c','a')) v(n,tenant);
update vouch.submissions set current_version_id=pg_temp.retention_id('version-a')
where id=pg_temp.retention_id('submission-a');
insert into vouch.analyses(id,organization_id,submission_version_id,analysis_status,machine_assessment,
  manifest_hash,invocation_mode,scenario,required_coverage,observed_coverage,missing_intervals,
  model_versions,prompt_version,schema_version,created_at)
select pg_temp.retention_id('analysis-'||n),pg_temp.retention_id('org-'||tenant),
  pg_temp.retention_id('version-'||n),'running','uncertain',repeat('c',64),'fixture','clean',
  '["speech"]','["speech"]','[]','{}','fixture-v1','1',now()
from (values('a','a'),('b','b'),('c','a')) v(n,tenant);
insert into vouch.fix_request_drafts
  (id,organization_id,analysis_id,text,created_by,created_at)
select pg_temp.retention_id('feedback-draft-'||n),pg_temp.retention_id('org-'||tenant),
  pg_temp.retention_id('analysis-'||n),'Internal draft '||n,pg_temp.retention_id('user'),now()
from (values('a','a'),('b','b'),('c','a')) v(n,tenant);
insert into vouch.analyses(id,organization_id,submission_version_id,analysis_status,machine_assessment,
  manifest_hash,invocation_mode,scenario,required_coverage,observed_coverage,missing_intervals,
  model_versions,prompt_version,schema_version,created_at,completed_at)
values(pg_temp.retention_id('feedback-analysis-a'),pg_temp.retention_id('org-a'),
  pg_temp.retention_id('version-a'),'completed','issues_found',repeat('f',64),'fixture','clean',
  '["speech"]','["speech"]','[]','{}','fixture-v1','1',now(),now());
insert into vouch.fix_request_drafts
  (id,organization_id,analysis_id,text,created_by,created_at)
values(pg_temp.retention_id('feedback-publish-draft-a'),pg_temp.retention_id('org-a'),
  pg_temp.retention_id('feedback-analysis-a'),'Published creator guidance',
  pg_temp.retention_id('user'),now());
insert into vouch.review_contexts(id,organization_id,analysis_id,submission_id,submission_version_id,
  review_status,revision,manifest_hash)
values(pg_temp.retention_id('feedback-context-a'),pg_temp.retention_id('org-a'),
  pg_temp.retention_id('feedback-analysis-a'),pg_temp.retention_id('submission-a'),
  pg_temp.retention_id('version-a'),'unreviewed',1,repeat('f',64));
insert into vouch.consent_receipts (
  id,organization_id,asset_id,campaign_id,actor_user_id,purpose,
  notice_version,notice_hash,accepted_at
) values (
  pg_temp.retention_id('feedback-consent-a'),pg_temp.retention_id('org-a'),
  pg_temp.retention_id('asset-a'),pg_temp.retention_id('campaign-a'),
  pg_temp.retention_id('user'),'campaign_check','retention-feedback-notice-v1',
  repeat('9',64),now()
);
-- Feedback is published while the source is active, then the expiry fixtures are
-- backdated so the scrub path follows the same anchored lineage as production.
update vouch.media_assets set retention_deadline=now()+interval '1 day'
where id=pg_temp.retention_id('asset-a');
insert into vouch.creator_feedback (
  id,organization_id,submission_id,submission_version_id,analysis_id,
  fix_request_draft_id,message,start_ms,end_ms,invocation_mode,analysis_status,
  manifest_hash,published_by_user_id,idempotency_key,request_digest,published_at
)
values(pg_temp.retention_id('feedback-a'),pg_temp.retention_id('org-a'),
  pg_temp.retention_id('submission-a'),pg_temp.retention_id('version-a'),
  pg_temp.retention_id('feedback-analysis-a'),pg_temp.retention_id('feedback-publish-draft-a'),
  'Published feedback a',null,null,'fixture','completed',repeat('f',64),
  pg_temp.retention_id('user'),'retention-feedback-a',repeat('a',64),now());
update vouch.media_assets set retention_deadline=now()-interval '1 day'
where id in (pg_temp.retention_id('asset-a'),pg_temp.retention_id('asset-b'));
insert into vouch.jobs(id,organization_id,kind,resource_id,logical_key,status,attempt_count,
  max_attempts,fence,scenario,created_at,updated_at)
select pg_temp.retention_id('job-'||n),pg_temp.retention_id('org-'||tenant),'check',
  pg_temp.retention_id('analysis-'||n),'retention-job-'||n,'running',1,3,1,'clean',now(),now()
from (values('a','a'),('b','b'),('c','a')) v(n,tenant);
insert into vouch.budget_reservations(id,organization_id,job_id,logical_key,held_minor,
  settled_minor,currency,status,price_snapshot,created_at)
select pg_temp.retention_id('budget-'||n),pg_temp.retention_id('org-a'),
  pg_temp.retention_id('job-'||n),'retention-budget-'||n,amount,0,'USD','held',0,now()
from (values('a',5),('c',7)) v(n,amount);
insert into vouch.evidence_items(id,organization_id,analysis_id,modality,precision,description,captured_at)
values(pg_temp.retention_id('evidence'),pg_temp.retention_id('org-a'),pg_temp.retention_id('analysis-a'),
  'speech','fixture','Source evidence',now());
insert into vouch.findings(id,organization_id,analysis_id,rule_id,rule_version,severity,evidence_ids,
  evidence_text,uncertainty,suggested_action,fingerprint,created_at)
values(pg_temp.retention_id('finding'),pg_temp.retention_id('org-a'),pg_temp.retention_id('analysis-a'),
  'fixture','1','warning','[]','Source finding','uncertain','Source action',repeat('d',64),now());
insert into vouch.review_contexts(id,organization_id,analysis_id,submission_id,submission_version_id,
  review_status,revision,manifest_hash)
values(pg_temp.retention_id('context'),pg_temp.retention_id('org-a'),pg_temp.retention_id('analysis-a'),
  pg_temp.retention_id('submission-a'),pg_temp.retention_id('version-a'),'approved',1,repeat('e',64));

select ok((select not rolcanlogin and not rolsuper and not rolbypassrls and not rolcreaterole
  from pg_roles where rolname='vouch_retention'),'retention group has no login or bypass');
select ok(not pg_has_role('vouch_retention','vouch_api','member')
  and not pg_has_role('vouch_retention','vouch_worker','member'),'retention is independent of API/Check roles');
select ok(not has_table_privilege('vouch_retention','vouch.users','SELECT,INSERT,UPDATE,DELETE'),
  'retention has no identity access');
select ok(not has_table_privilege('vouch_retention','vouch.membership_roles','INSERT,UPDATE,DELETE'),
  'retention cannot grant human roles');
select ok(not has_table_privilege('vouch_retention','vouch.approvals','INSERT,UPDATE,DELETE'),
  'retention cannot write human approvals');
select ok(not has_table_privilege('vouch_retention','vouch.findings','INSERT'),
  'retention cannot manufacture machine findings');
select ok(not has_column_privilege('vouch_retention','vouch.media_assets','retention_deadline','UPDATE'),
  'retention cannot extend the original deadline');
select ok(not has_column_privilege('vouch_retention','vouch.deletion_requests','max_attempts','UPDATE'),
  'retention cannot replenish automatic retry budget');
select ok(
  has_table_privilege('vouch_retention','vouch.creator_feedback','SELECT')
  and has_column_privilege('vouch_retention','vouch.creator_feedback','message','UPDATE')
  and has_column_privilege('vouch_retention','vouch.creator_feedback','start_ms','UPDATE')
  and has_column_privilege('vouch_retention','vouch.creator_feedback','end_ms','UPDATE')
  and not has_column_privilege(
    'vouch_retention','vouch.creator_feedback','manifest_hash','UPDATE'
  )
  and not has_table_privilege('vouch_retention','vouch.creator_feedback','INSERT,DELETE'),
  'retention can read scoped feedback and erase only its shared content snapshot'
);
select ok(not has_function_privilege('anon','vouch_private.retention_expired_assets(integer)','EXECUTE')
  and not has_function_privilege('vouch_api','vouch_private.retention_expired_assets(integer)','EXECUTE'),
  'global identifier discovery is not a client/member capability');

set local role vouch_retention;
select is((select count(*)::integer from vouch.media_assets),0,'no scope reveals no source bytes');
select is((select count(*)::integer from vouch.submission_versions),0,'no scope reveals no captions');
select is((select count(*)::integer from vouch.creator_feedback),0,
  'no scope reveals no published creator feedback');
select is((select count(*)::integer from vouch_private.retention_expired_assets(100)
  where id in (pg_temp.retention_id('asset-a'),pg_temp.retention_id('asset-b'),pg_temp.retention_id('asset-orphan'))),
  3,'identifier discovery includes expired assets and abandoned intents across tenants');
select is((select count(*)::integer from vouch_private.retention_expired_assets(100)
  where id=pg_temp.retention_id('asset-c')),0,'discovery excludes nonexpired sources');
select set_config('vouch.organization_id',pg_temp.retention_id('org-a')::text,true);
select set_config('vouch.retention_asset_id',pg_temp.retention_id('asset-a')::text,true);
select is((select count(*)::integer from vouch.media_assets),1,'exact expiry anchor reveals one source');
select is((select count(*)::integer from vouch.submission_versions),1,'derivative read follows exact asset lineage');
select is((select count(*)::integer from vouch.jobs),1,'work read follows exact asset lineage');
select is((select count(*)::integer from vouch.creator_feedback),1,
  'published feedback read follows only the exact expired source lineage');
with changed as (update vouch.media_assets set filename='',status='deleted',object_bytes=null,deleted_at=now()
  where id=pg_temp.retention_id('asset-b') returning id)
select is((select count(*)::integer from changed),0,'other-tenant source update denied');
with changed as (update vouch.media_assets set filename='',status='deleted',object_bytes=null,deleted_at=now()
  where id=pg_temp.retention_id('asset-c') returning id)
select is((select count(*)::integer from changed),0,'nonexpired source update denied');
select throws_ok($$update vouch.media_assets set filename='replacement.mp4'
  where id=pg_temp.retention_id('asset-a')$$,'42501',null,'expired source cannot be rewritten');
select throws_ok($$update vouch.media_assets set retention_deadline=now()+interval '1 year'
  where id=pg_temp.retention_id('asset-a')$$,'42501',null,'deadline mutation denied by column grant');
select throws_ok($$update vouch.submissions set current_version_id=null
  where id=pg_temp.retention_id('submission-a')$$,'42501',null,'source lock does not allow pointer edits');
select throws_ok($$update vouch.submission_versions set caption='replacement'
  where id=pg_temp.retention_id('version-a')$$,'42501',null,'caption may only be erased');
select throws_ok($$update vouch.analyses set analysis_status='completed',machine_assessment='no_issues_detected'
  where id=pg_temp.retention_id('analysis-a')$$,'42501',null,'retention cannot publish success');
select throws_ok($$update vouch.review_contexts set review_status='approved',revision=2
  where id=pg_temp.retention_id('context')$$,'42501',null,'retention cannot create an approval state');
select throws_ok($$update vouch.evidence_items set description='replacement'$$,'42501',null,
  'evidence may only be erased');
select throws_ok($$update vouch.creator_feedback set message='replacement'
  where id=pg_temp.retention_id('feedback-a')$$,'42501',null,
  'published creator feedback may only be erased');
select throws_ok($$update vouch.creator_feedback set manifest_hash=repeat('f',64)
  where id=pg_temp.retention_id('feedback-a')$$,'42501',null,
  'retention cannot rewrite shared feedback provenance');
select throws_ok($$update vouch.organizations set budget_held_minor=0
  where id=pg_temp.retention_id('org-a')$$,'42501',null,'unreleased holds cannot be removed');
select lives_ok($$update vouch.media_assets set filename='',status='deleted',object_bytes=null,deleted_at=now()
  where id=pg_temp.retention_id('asset-a')$$,'system erases the exact expired source');
select lives_ok($$update vouch.submission_versions set caption='' where id=pg_temp.retention_id('version-a')$$,
  'system erases source caption');
select lives_ok($$update vouch.analyses set analysis_status='cancelled',machine_assessment='not_assessed',
  observed_coverage='[]',missing_intervals='[]',completed_at=now() where id=pg_temp.retention_id('analysis-a')$$,
  'system cancels and clears machine assessment');
select lives_ok($$update vouch.jobs set status='cancelled',fence=fence+1,lease_owner=null,
  lease_until=null,retry_after=null,updated_at=now() where id=pg_temp.retention_id('job-a')$$,
  'system fences expired-source Check work');
select lives_ok($$update vouch.budget_reservations set status='released',reconciled_at=now()
  where id=pg_temp.retention_id('budget-a')$$,'only cancelled source hold is released');
select lives_ok($$update vouch.organizations set budget_held_minor=7 where id=pg_temp.retention_id('org-a')$$,
  'budget aggregate matches remaining live holds');
select throws_ok($$update vouch.organizations set budget_held_minor=0 where id=pg_temp.retention_id('org-a')$$,
  '42501',null,'system cannot release a second unrelated hold');
select lives_ok($$update vouch.review_contexts set review_status='revoked',revision=revision+1
  where id=pg_temp.retention_id('context')$$,'system invalidates prior human approval lineage');
select lives_ok($$update vouch.evidence_items set description='';
  update vouch.findings set evidence_text='',uncertainty='',suggested_action=''$$,
  'system erases timestamped evidence and finding text');
select lives_ok($$update vouch.creator_feedback set message='',start_ms=null,end_ms=null
  where id=pg_temp.retention_id('feedback-a')$$,
  'system erases the exact published feedback snapshot');
select is((select message from vouch.creator_feedback
  where id=pg_temp.retention_id('feedback-a')),''::text,
  'feedback identifiers and provenance remain after content scrubbing');
select lives_ok($$insert into vouch.tombstones(id,organization_id,resource_type,resource_id,created_at)
  values(pg_temp.retention_id('tombstone'),pg_temp.retention_id('org-a'),'media_asset',
    pg_temp.retention_id('asset-a'),now())$$,'system persists a narrow source tombstone');
select lives_ok($$insert into vouch.deletion_requests(id,organization_id,resource_type,resource_id,
  status,destinations,requested_by,requested_by_kind,created_at)
  values(pg_temp.retention_id('receipt'),pg_temp.retention_id('org-a'),'media_asset',
    pg_temp.retention_id('asset-a'),'partial','[{"destination":"local_fixture_database","status":"completed"}]',
    null,'retention',now())$$,'system receipt has no impersonated member');
select lives_ok($$insert into vouch.audit_events(id,organization_id,actor_user_id,actor_kind,action,
  resource_type,resource_id,safe_metadata,created_at)
  values(pg_temp.retention_id('audit'),pg_temp.retention_id('org-a'),null,'retention','deletion.requested',
    'deletion_request',pg_temp.retention_id('receipt'),'{}',now())$$,'system audit is explicitly attributed');
select throws_ok($$insert into vouch.audit_events(id,organization_id,actor_user_id,actor_kind,action,
  resource_type,resource_id,safe_metadata,created_at)
  values(pg_temp.retention_id('bad-audit'),pg_temp.retention_id('org-a'),pg_temp.retention_id('user'),
    'member','deletion.requested','deletion_request',pg_temp.retention_id('receipt'),'{}',now())$$,
  '42501',null,'system cannot impersonate member audit');
select set_config('vouch.retention_asset_id','',true);
select is((select count(*)::integer from vouch.deletion_requests),0,'receipt scope does not leak between items');
select set_config('vouch.retention_request_id',pg_temp.retention_id('receipt')::text,true);
select is((select count(*)::integer from vouch.deletion_requests),1,'exact receipt can be reconciled after restart');
select is((select count(*)::integer from vouch.media_assets),1,'receipt resolves only its tombstoned source key');
select lives_ok($$update vouch.deletion_requests set attempt_count=attempt_count+1,fence=fence+1,
  lease_owner='retention-test',lease_until=now()+interval '60 seconds'
  where id=pg_temp.retention_id('receipt')$$,'claim advances fence and attempt together');
select throws_ok($$update vouch.deletion_requests set fence=fence+1 where id=pg_temp.retention_id('receipt')$$,
  '42501',null,'independent fence mutation denied');
select throws_ok($$update vouch.deletion_requests set attempt_count=0 where id=pg_temp.retention_id('receipt')$$,
  '42501',null,'automatic retry counter cannot be reset');
select throws_ok($$update vouch.deletion_requests set destinations='[]' where id=pg_temp.retention_id('receipt')$$,
  '42501',null,'claim cannot swap cleanup destinations');
select lives_ok($$update vouch.deletion_requests set status='completed',completed_at=now(),lease_owner=null,
  lease_until=null where id=pg_temp.retention_id('receipt')$$,'current claim publishes completion');
select throws_ok($$update vouch.deletion_requests set status='partial' where id=pg_temp.retention_id('receipt')$$,
  '42501',null,'completed erasure receipt is terminal');
select set_config('vouch.organization_id',pg_temp.retention_id('org-b')::text,true);
select is((select count(*)::integer from vouch.deletion_requests),0,'wrong tenant cannot claim a known receipt');

reset role;
-- A corrupt receipt must never broaden source authority to an active source merely by
-- listing its identifier. Reconciliation only resolves already tombstoned same-tenant keys.
insert into vouch.deletion_requests(id,organization_id,resource_type,resource_id,status,destinations,
  requested_by,requested_by_kind,created_at)
values(pg_temp.retention_id('member-receipt'),pg_temp.retention_id('org-a'),'submission',
  pg_temp.retention_id('submission-a'),'partial',jsonb_build_array(jsonb_build_object(
    'destination','supabase_storage','status','pending','asset_ids',jsonb_build_array(
      pg_temp.retention_id('asset-a')::text,pg_temp.retention_id('asset-c')::text))),
  pg_temp.retention_id('user'),'member',now());
select set_config('vouch.organization_id',pg_temp.retention_id('org-a')::text,true);
select set_config('vouch.retention_request_id',pg_temp.retention_id('member-receipt')::text,true);
set local role vouch_retention;
select is((select count(*)::integer from vouch.media_assets),1,
  'member receipt only grants cleanup lookup for already erased source');
select is((select count(*)::integer from vouch.media_assets where id=pg_temp.retention_id('asset-c')),0,
  'corrupt receipt destination cannot reveal active source bytes');
select is((select count(*)::integer from vouch_private.retention_pending_requests(100)
  where id=pg_temp.retention_id('member-receipt')),1,'incomplete member cleanup is discovered after restart');
select lives_ok($$update vouch.deletion_requests set attempt_count=1,fence=1,
  lease_owner='first-worker',lease_until=now()+interval '60 seconds'
  where id=pg_temp.retention_id('member-receipt')$$,'system may claim pending member-authorized cleanup');
select is((select count(*)::integer from vouch_private.retention_pending_requests(100)
  where id=pg_temp.retention_id('member-receipt')),0,'active lease is not rediscovered');
select throws_ok($$update vouch.deletion_requests set lease_owner='other-worker'
  where id=pg_temp.retention_id('member-receipt')$$,'42501',null,
  'lease cannot be stolen without a new fence');
select throws_ok($$update vouch.deletion_requests set attempt_count=2,fence=2,
  lease_owner='other-worker',lease_until=now()+interval '60 seconds'
  where id=pg_temp.retention_id('member-receipt')$$,'42501',null,
  'active claim cannot be reclaimed before expiration');
with changed as(update vouch.deletion_requests set status='completed',completed_at=now(),
  lease_owner=null,lease_until=null where id=pg_temp.retention_id('member-receipt') and fence=0 returning id)
select is((select count(*)::integer from changed),0,'stale fence cannot publish a cleanup result');
select throws_ok($$update vouch.deletion_requests set max_attempts=10
  where id=pg_temp.retention_id('member-receipt')$$,'42501',null,'system retry limit is not editable');
reset role;
update vouch.deletion_requests set attempt_count=3,fence=3,lease_owner=null,lease_until=null,status='partial'
where id=pg_temp.retention_id('member-receipt');
set local role vouch_retention;
select throws_ok($$update vouch.deletion_requests set attempt_count=4,fence=4,
  lease_owner='fourth-worker',lease_until=now()+interval '60 seconds'
  where id=pg_temp.retention_id('member-receipt')$$,'42501',null,
  'system cannot claim a fourth automatic cleanup attempt');
select lives_ok($$update vouch.deletion_requests set status='failed',last_error_code='RETRIES_EXHAUSTED'
  where id=pg_temp.retention_id('member-receipt')$$,'exhausted cleanup retains a visible failure receipt');
select is((select count(*)::integer from vouch_private.retention_pending_requests(100)
  where id=pg_temp.retention_id('member-receipt')),0,'failed receipt is excluded from automatic retries');
reset role;
-- A retention receipt's external-copy declarations must resolve to the exact expired,
-- erased source. A known same-tenant live run name is not an erasure capability.
update vouch.media_assets set storage_backend='supabase',object_key=
  organization_id::text||'/'||campaign_id::text||'/'||id::text||'/source',
  processing_container='vouch-media-'||replace(organization_id::text,'-','')||'-'
    ||replace(id::text,'-','')||'-'||repeat('a',32)
where id=pg_temp.retention_id('asset-a');
update vouch.media_assets set processing_container='vouch-media-'
  ||replace(organization_id::text,'-','')||'-'||replace(id::text,'-','')||'-'||repeat('b',32)
where id=pg_temp.retention_id('asset-c');
create function pg_temp.retention_payload(target uuid, container_name text) returns jsonb
language sql immutable as $$
  select jsonb_build_array(
    jsonb_build_object('destination','supabase_storage','status','pending',
      'asset_ids',jsonb_build_array(target::text)),
    jsonb_build_object('destination','local_media_sandbox','status','pending',
      'asset_ids',jsonb_build_array(target::text),'container_names',jsonb_build_array(container_name)))
$$;
create function pg_temp.retention_insert_receipt(label text, payload jsonb) returns void
language sql as $$
  insert into vouch.deletion_requests(id,organization_id,resource_type,resource_id,status,destinations,
    requested_by,requested_by_kind,created_at)
  values(pg_temp.retention_id('bound-'||label),pg_temp.retention_id('org-a'),'media_asset',
    pg_temp.retention_id('asset-a'),'partial',payload,null,'retention',now())
$$;
select set_config('vouch.organization_id',pg_temp.retention_id('org-a')::text,true);
select set_config('vouch.retention_asset_id',pg_temp.retention_id('asset-a')::text,true);
select set_config('vouch.retention_request_id','',true);
select set_config('vouch.test_anchor_name',(select processing_container from vouch.media_assets
  where id=pg_temp.retention_id('asset-a')),true);
select set_config('vouch.test_live_name',(select processing_container from vouch.media_assets
  where id=pg_temp.retention_id('asset-c')),true);
select ok(not has_function_privilege('anon',
  'vouch_private.retention_destinations_allowed(uuid,uuid,jsonb)','EXECUTE')
  and not has_function_privilege('vouch_api',
  'vouch_private.retention_destinations_allowed(uuid,uuid,jsonb)','EXECUTE'),
  'destination binding helper is private system authority');
set local role vouch_retention;
select lives_ok($$select pg_temp.retention_insert_receipt('valid',pg_temp.retention_payload(
  pg_temp.retention_id('asset-a'),current_setting('vouch.test_anchor_name')))$$,
  'system can declare exact erased source Storage and sandbox copies');
select throws_ok($$select pg_temp.retention_insert_receipt('live-name',pg_temp.retention_payload(
  pg_temp.retention_id('asset-a'),current_setting('vouch.test_live_name')))$$,'42501',null,
  'known same-tenant live container cannot be attached to expired anchor receipt');
select throws_ok($$select pg_temp.retention_insert_receipt('live-asset',pg_temp.retention_payload(
  pg_temp.retention_id('asset-c'),current_setting('vouch.test_live_name')))$$,'42501',null,
  'receipt cannot substitute a nonexpired same-tenant asset');
select throws_ok($$select pg_temp.retention_insert_receipt('other-tenant',pg_temp.retention_payload(
  pg_temp.retention_id('asset-b'),'vouch-media-'||replace(pg_temp.retention_id('org-b')::text,'-','')
    ||'-'||replace(pg_temp.retention_id('asset-b')::text,'-','')||'-'||repeat('c',32)))$$,'42501',null,
  'receipt cannot substitute another tenant source or sandbox');
select throws_ok($$select pg_temp.retention_insert_receipt('wrong-run',pg_temp.retention_payload(
  pg_temp.retention_id('asset-a'),left(current_setting('vouch.test_anchor_name'),length(
    current_setting('vouch.test_anchor_name'))-32)||repeat('f',32)))$$,'42501',null,
  'correct asset prefix does not authorize a different run reference');
select throws_ok($$select pg_temp.retention_insert_receipt('wrong-storage',jsonb_set(
  pg_temp.retention_payload(pg_temp.retention_id('asset-a'),current_setting('vouch.test_anchor_name')),
  '{0,asset_ids}',jsonb_build_array(pg_temp.retention_id('asset-c')::text)))$$,'42501',null,
  'Storage declaration cannot substitute a live asset identifier');
select throws_ok($$select pg_temp.retention_insert_receipt('extra-asset',jsonb_set(
  pg_temp.retention_payload(pg_temp.retention_id('asset-a'),current_setting('vouch.test_anchor_name')),
  '{1,asset_ids}',jsonb_build_array(pg_temp.retention_id('asset-a')::text,
    pg_temp.retention_id('asset-c')::text)))$$,'42501',null,
  'sandbox declaration cannot append extra asset capabilities');
select throws_ok($$select pg_temp.retention_insert_receipt('missing-sandbox',jsonb_build_array(
  pg_temp.retention_payload(pg_temp.retention_id('asset-a'),current_setting('vouch.test_anchor_name'))->0))$$,
  '42501',null,'system receipt cannot omit a known temporary copy');
select throws_ok($$select pg_temp.retention_insert_receipt('missing-storage',jsonb_build_array(
  pg_temp.retention_payload(pg_temp.retention_id('asset-a'),current_setting('vouch.test_anchor_name'))->1))$$,
  '42501',null,'system receipt cannot omit a known Storage copy');
select throws_ok($$select pg_temp.retention_insert_receipt('duplicate',
  pg_temp.retention_payload(pg_temp.retention_id('asset-a'),current_setting('vouch.test_anchor_name'))
  ||jsonb_build_array(pg_temp.retention_payload(pg_temp.retention_id('asset-a'),
    current_setting('vouch.test_anchor_name'))->1))$$,'42501',null,
  'duplicate destinations cannot hide an unprocessed copy declaration');
select throws_ok($$select pg_temp.retention_insert_receipt('malformed','{}')$$,'42501',null,
  'malformed declaration is rejected without granting source authority');
reset role;
select * from finish();
rollback;
