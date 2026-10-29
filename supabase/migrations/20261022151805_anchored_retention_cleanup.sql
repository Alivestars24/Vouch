-- Local-only anchored retention authority. No application data is reset or migrated away.
alter table vouch.deletion_requests
  alter column requested_by drop not null,
  add column requested_by_kind varchar(24) not null default 'member',
  add column attempt_count integer not null default 0,
  add column max_attempts integer not null default 3,
  add column retry_after timestamptz,
  add column lease_owner varchar(100),
  add column lease_until timestamptz,
  add column fence integer not null default 0,
  add column last_error_code varchar(64),
  add constraint deletion_actor check (
    (requested_by_kind = 'member' and requested_by is not null)
    or (requested_by_kind = 'retention' and requested_by is null)),
  add constraint deletion_attempts check (attempt_count >= 0 and max_attempts = 3 and fence >= 0);
create index ix_retention_expiry on vouch.media_assets (retention_deadline, id)
  where deleted_at is null and status <> 'deleted';
create index ix_deletion_claim on vouch.deletion_requests (retry_after, lease_until, id)
  where status not in ('completed','failed');

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'vouch_retention') then
    create role vouch_retention nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end $$;
grant usage on schema vouch, vouch_private to vouch_retention;
grant execute on function vouch_private.organization_id() to vouch_retention;

create function vouch_private.retention_asset_id() returns uuid
language sql stable set search_path = '' as $$
  select nullif(current_setting('vouch.retention_asset_id', true), '')::uuid
$$;
create function vouch_private.retention_request_id() returns uuid
language sql stable set search_path = '' as $$
  select nullif(current_setting('vouch.retention_request_id', true), '')::uuid
$$;

-- Discovery deliberately returns identifiers only, never global source bytes or captions.
-- These private fixed-search-path owner lookups avoid recursive RLS; they perform no writes.
create function vouch_private.retention_expired_assets(batch_limit integer default 1)
returns table(id uuid, organization_id uuid)
language sql stable security definer set search_path = '' as $$
  select ma.id, ma.organization_id from vouch.media_assets ma
  where ma.retention_deadline <= now() and ma.deleted_at is null and ma.status <> 'deleted'
  order by ma.retention_deadline, ma.id limit greatest(1, least(batch_limit, 100))
$$;
create function vouch_private.retention_pending_requests(batch_limit integer default 1)
returns table(id uuid, organization_id uuid)
language sql stable security definer set search_path = '' as $$
  select dr.id, dr.organization_id from vouch.deletion_requests dr
  where dr.status not in ('completed','failed')
    and (dr.retry_after is null or dr.retry_after <= now())
    and (dr.lease_until is null or dr.lease_until <= now())
  order by dr.created_at, dr.id limit greatest(1, least(batch_limit, 100))
$$;
create function vouch_private.retention_request_allowed(target uuid, tenant uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select tenant = vouch_private.organization_id() and exists (
    select 1 from vouch.deletion_requests dr
    where dr.id = target and dr.organization_id = tenant
      and (dr.id = vouch_private.retention_request_id()
        or (dr.resource_type = 'media_asset' and dr.resource_id = vouch_private.retention_asset_id()
          and exists (select 1 from vouch.media_assets ma
            where ma.id = dr.resource_id and ma.organization_id = tenant
              and ma.retention_deadline <= now())))
  )
$$;
create function vouch_private.retention_asset_allowed(target uuid, tenant uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select tenant = vouch_private.organization_id() and exists (
    select 1 from vouch.media_assets ma where ma.id = target and ma.organization_id = tenant
      and ((ma.id = vouch_private.retention_asset_id() and ma.retention_deadline <= now())
        or (ma.deleted_at is not null and ma.status = 'deleted' and exists (
          select 1 from vouch.deletion_requests dr
          where dr.id = vouch_private.retention_request_id() and dr.organization_id = tenant
            and ((dr.resource_type = 'media_asset' and dr.resource_id = ma.id)
              or exists (select 1 from jsonb_array_elements(dr.destinations::jsonb) d
                where d->>'destination' = 'supabase_storage'
                  and coalesce(d->'asset_ids','[]'::jsonb) ? ma.id::text)))))
  )
$$;
create function vouch_private.retention_version_allowed(target uuid, tenant uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from vouch.submission_versions sv
    where sv.id = target and sv.organization_id = tenant
      and vouch_private.retention_asset_allowed(sv.asset_id, tenant))
$$;
create function vouch_private.retention_submission_allowed(target uuid, tenant uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from vouch.submission_versions sv
    where sv.submission_id = target and sv.organization_id = tenant
      and vouch_private.retention_asset_allowed(sv.asset_id, tenant))
$$;
create function vouch_private.retention_analysis_allowed(target uuid, tenant uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from vouch.analyses a where a.id = target and a.organization_id = tenant
    and vouch_private.retention_version_allowed(a.submission_version_id, tenant))
$$;
create function vouch_private.retention_context_allowed(target uuid, tenant uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from vouch.review_contexts rc
    where rc.id = target and rc.organization_id = tenant
      and vouch_private.retention_analysis_allowed(rc.analysis_id, tenant))
$$;
create function vouch_private.retention_finding_allowed(target uuid, tenant uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from vouch.findings f where f.id = target and f.organization_id = tenant
    and vouch_private.retention_analysis_allowed(f.analysis_id, tenant))
$$;
create function vouch_private.retention_job_allowed(target uuid, tenant uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from vouch.jobs j where j.id = target and j.organization_id = tenant
    and j.kind = 'check' and vouch_private.retention_analysis_allowed(j.resource_id, tenant))
$$;
create function vouch_private.retention_scope_active(tenant uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select tenant = vouch_private.organization_id()
    and (vouch_private.retention_asset_allowed(vouch_private.retention_asset_id(), tenant)
      or vouch_private.retention_request_allowed(vouch_private.retention_request_id(), tenant))
$$;
create function vouch_private.retention_held_total(tenant uuid) returns bigint
language sql stable security definer set search_path = '' as $$
  select case when vouch_private.retention_scope_active(tenant)
    then (select coalesce(sum(br.held_minor),0) from vouch.budget_reservations br
      where br.organization_id = tenant and br.status = 'held') else null end
$$;

-- Revoke explicitly despite the private schema's restrictive default privileges.
do $$ declare signature regprocedure; begin
  for signature in select p.oid::regprocedure from pg_proc p join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='vouch_private' and p.proname like 'retention\_%' escape '\' loop
    execute format('revoke all on function %s from public, anon, authenticated, vouch_api, vouch_worker', signature);
    execute format('grant execute on function %s to vouch_retention', signature);
  end loop;
end $$;

grant select on vouch.organizations, vouch.media_assets, vouch.submissions,
  vouch.submission_versions, vouch.analyses, vouch.review_contexts, vouch.jobs,
  vouch.budget_reservations, vouch.evidence_items, vouch.findings, vouch.finding_decisions,
  vouch.review_events, vouch.fix_request_drafts, vouch.tombstones, vouch.deletion_requests
  to vouch_retention;
create policy retention_org_read on vouch.organizations for select to vouch_retention
  using (vouch_private.retention_scope_active(id));
create policy retention_receipt_read on vouch.deletion_requests for select to vouch_retention
  using (vouch_private.retention_request_allowed(id,organization_id));
do $$ declare relation text; predicate text; begin
  for relation,predicate in select * from (values
    ('media_assets','vouch_private.retention_asset_allowed(id,organization_id)'),
    ('submissions','vouch_private.retention_submission_allowed(id,organization_id)'),
    ('submission_versions','vouch_private.retention_version_allowed(id,organization_id)'),
    ('analyses','vouch_private.retention_analysis_allowed(id,organization_id)'),
    ('review_contexts','vouch_private.retention_context_allowed(id,organization_id)'),
    ('jobs','vouch_private.retention_job_allowed(id,organization_id)'),
    ('budget_reservations','vouch_private.retention_job_allowed(job_id,organization_id)'),
    ('evidence_items','vouch_private.retention_analysis_allowed(analysis_id,organization_id)'),
    ('findings','vouch_private.retention_analysis_allowed(analysis_id,organization_id)'),
    ('finding_decisions','vouch_private.retention_finding_allowed(finding_id,organization_id)'),
    ('review_events','vouch_private.retention_context_allowed(review_context_id,organization_id)'),
    ('fix_request_drafts','vouch_private.retention_analysis_allowed(analysis_id,organization_id)'),
    ('tombstones','(resource_type = ''media_asset'' and vouch_private.retention_asset_allowed(resource_id,organization_id)) or (resource_type = ''submission'' and vouch_private.retention_submission_allowed(resource_id,organization_id))')
  ) p(relation,predicate) loop
    execute format('create policy retention_read on vouch.%I for select to vouch_retention using (%s)',relation,predicate);
    if relation <> 'tombstones' then
      execute format('create policy retention_scrub on vouch.%I for update to vouch_retention using (%s) with check (%s)',relation,predicate,predicate);
    end if;
  end loop;
end $$;
grant update (filename,object_bytes,status,deleted_at) on vouch.media_assets to vouch_retention;
-- Locks only: trigger below prevents any pointer or source mutation on submissions.
grant update (current_version_id) on vouch.submissions to vouch_retention;
grant update (caption) on vouch.submission_versions to vouch_retention;
grant update (analysis_status,machine_assessment,observed_coverage,missing_intervals,completed_at)
  on vouch.analyses to vouch_retention;
grant update (revision,review_status) on vouch.review_contexts to vouch_retention;
grant update (status,fence,lease_owner,lease_until,retry_after,updated_at) on vouch.jobs to vouch_retention;
grant update (status,reconciled_at) on vouch.budget_reservations to vouch_retention;
grant update (budget_held_minor) on vouch.organizations to vouch_retention;
create policy retention_budget_release on vouch.organizations for update to vouch_retention
  using (vouch_private.retention_scope_active(id)) with check (vouch_private.retention_scope_active(id));
grant update (description) on vouch.evidence_items to vouch_retention;
grant update (evidence_text,uncertainty,suggested_action) on vouch.findings to vouch_retention;
grant update (rationale) on vouch.finding_decisions,vouch.review_events to vouch_retention;
grant update (text) on vouch.fix_request_drafts to vouch_retention;
grant insert on vouch.tombstones,vouch.deletion_requests,vouch.audit_events to vouch_retention;
create policy retention_tombstone on vouch.tombstones for insert to vouch_retention
  with check (resource_type='media_asset'
    and resource_id=vouch_private.retention_asset_id()
    and vouch_private.retention_asset_allowed(resource_id,organization_id));
create policy retention_receipt_insert on vouch.deletion_requests for insert to vouch_retention
  with check (requested_by is null and requested_by_kind='retention'
    and resource_type='media_asset' and resource_id=vouch_private.retention_asset_id()
    and vouch_private.retention_asset_allowed(resource_id,organization_id)
    and exists (select 1 from vouch.media_assets ma where ma.id=resource_id
      and ma.organization_id=deletion_requests.organization_id and ma.status='deleted'
      and ma.deleted_at is not null));
create policy retention_receipt_update on vouch.deletion_requests for update to vouch_retention
  using (vouch_private.retention_request_allowed(id,organization_id))
  with check (vouch_private.retention_request_allowed(id,organization_id));
create policy retention_audit on vouch.audit_events for insert to vouch_retention
  with check (vouch_private.retention_scope_active(organization_id)
    and actor_kind='retention' and actor_user_id is null
    and action like 'deletion.%' and resource_type='deletion_request'
    and vouch_private.retention_request_allowed(resource_id,organization_id));
grant update (status,destinations,completed_at,attempt_count,retry_after,lease_owner,
  lease_until,fence,last_error_code) on vouch.deletion_requests to vouch_api,vouch_retention;
drop policy api_insert on vouch.deletion_requests;
create policy api_insert on vouch.deletion_requests for insert to vouch_api
  with check (vouch_private.has_role(organization_id,array['admin','marketer'])
    and requested_by=vouch_private.user_id() and requested_by_kind='member');

-- Column grants alone cannot distinguish erasure from forged replacement content.
create function vouch_private.guard_retention_scrub() returns trigger
language plpgsql set search_path = '' as $$
declare valid boolean := false;
begin
  if not (current_user='vouch_retention' or (pg_has_role(current_user,'vouch_retention','member')
    and not exists (select 1 from pg_catalog.pg_roles where rolname=current_user
      and (rolsuper or rolbypassrls)))) then return new; end if;
  if new is not distinct from old then return new; end if;
  case tg_table_name
    when 'media_assets' then valid := new.filename='' and new.object_bytes is null
      and new.status='deleted' and new.deleted_at is not null
      and to_jsonb(new)-array['filename','object_bytes','status','deleted_at']
        =to_jsonb(old)-array['filename','object_bytes','status','deleted_at'];
    when 'submissions' then valid := false;
    when 'submission_versions' then valid := new.caption='';
    when 'analyses' then valid := new.machine_assessment='not_assessed'
      and new.observed_coverage::jsonb='[]'::jsonb and new.missing_intervals::jsonb='[]'::jsonb
      and (new.analysis_status=old.analysis_status
        or (old.analysis_status in ('queued','running') and new.analysis_status='cancelled'));
    when 'review_contexts' then valid := new.review_status='revoked' and new.revision=old.revision+1;
    when 'jobs' then valid := old.status in ('queued','running','retry_wait')
      and new.status='cancelled' and new.fence=old.fence+1
      and new.lease_owner is null and new.lease_until is null and new.retry_after is null;
    when 'budget_reservations' then valid := old.status='held' and new.status='released'
      and new.reconciled_at is not null and exists (select 1 from vouch.jobs j
        where j.id=new.job_id and j.organization_id=new.organization_id and j.status='cancelled');
    when 'organizations' then valid := new.budget_held_minor<=old.budget_held_minor
      and new.budget_held_minor>=0
      and new.budget_held_minor=vouch_private.retention_held_total(new.id);
    when 'evidence_items' then valid := new.description='';
    when 'findings' then valid := new.evidence_text='' and new.uncertainty='' and new.suggested_action='';
    when 'finding_decisions','review_events' then valid := new.rationale='';
    when 'fix_request_drafts' then valid := new.text='';
    else valid := false;
  end case;
  if not coalesce(valid,false) then
    raise insufficient_privilege using message='Retention may only scrub anchored expired content';
  end if;
  return new;
end $$;
revoke all on function vouch_private.guard_retention_scrub() from public,anon,authenticated;
do $$ declare relation text; begin
  foreach relation in array array['media_assets','submissions','submission_versions','analyses',
    'review_contexts','jobs','budget_reservations','organizations','evidence_items','findings',
    'finding_decisions','review_events','fix_request_drafts'] loop
    execute format('create trigger guard_retention_scrub before update on vouch.%I for each row execute function vouch_private.guard_retention_scrub()',relation);
  end loop;
end $$;

-- Shared member/system receipt claims. The immutable scope and retry budget cannot change;
-- completion is terminal. Publication must retain its claim's fence and attempt number.
create function vouch_private.guard_deletion_receipt_update() returns trigger
language plpgsql set search_path = '' as $$
declare old_targets jsonb; new_targets jsonb;
begin
  if exists (select 1 from pg_catalog.pg_roles where rolname=current_user
    and (rolsuper or rolbypassrls)) then return new; end if;
  if new is not distinct from old then return new; end if;
  if old.status='completed' or to_jsonb(new)-array['status','destinations','completed_at',
    'attempt_count','retry_after','lease_owner','lease_until','fence','last_error_code']
    <>to_jsonb(old)-array['status','destinations','completed_at','attempt_count','retry_after',
    'lease_owner','lease_until','fence','last_error_code'] then
    raise insufficient_privilege using message='Deletion receipt scope and completion are immutable';
  end if;
  select jsonb_agg(d-'status') into old_targets from jsonb_array_elements(old.destinations::jsonb) d;
  select jsonb_agg(d-'status') into new_targets from jsonb_array_elements(new.destinations::jsonb) d;
  if old_targets is distinct from new_targets or new.fence<old.fence or new.fence>old.fence+1
    or new.attempt_count<old.attempt_count or new.attempt_count>old.attempt_count+1
    or ((new.fence=old.fence+1) <> (new.attempt_count=old.attempt_count+1))
    or (new.fence=old.fence+1 and (new.lease_owner is null or new.lease_until is null)) then
    raise insufficient_privilege using message='Deletion receipt claim or destinations are invalid';
  end if;
  return new;
end $$;
revoke all on function vouch_private.guard_deletion_receipt_update() from public,anon,authenticated;
create trigger guard_deletion_receipt_update before update on vouch.deletion_requests
  for each row execute function vouch_private.guard_deletion_receipt_update();
