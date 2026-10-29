-- Accepted authenticated-foundation contract. Apply locally until hosted rollout is approved.
alter table vouch.users add column auth_subject uuid unique;
alter table vouch.media_assets
  add column storage_backend varchar(32) not null default 'database',
  add column object_key varchar(500);

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'vouch_api') then
    create role vouch_api nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'vouch_worker') then
    create role vouch_worker nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end $$;

create schema vouch_private;
revoke all on schema vouch_private from public, anon, authenticated;
grant usage on schema vouch to vouch_api, vouch_worker;
grant usage on schema vouch_private to vouch_api, vouch_worker, authenticated;
alter default privileges in schema vouch_private revoke execute on functions from public;

-- API context is set only after server verification, never from JWT role/metadata claims.
create function vouch_private.subject_id() returns uuid
language sql stable set search_path = '' as $$
  select nullif(current_setting('vouch.auth_subject', true), '')::uuid
$$;
create function vouch_private.user_id() returns uuid
language sql stable set search_path = '' as $$
  select nullif(current_setting('vouch.user_id', true), '')::uuid
$$;
create function vouch_private.organization_id() returns uuid
language sql stable set search_path = '' as $$
  select nullif(current_setting('vouch.organization_id', true), '')::uuid
$$;

-- Deliberately narrow definer lookups avoid recursive membership RLS. The schema is not
-- exposed to PostgREST; no browser role can invoke the server-context helpers.
create function vouch_private.member_of(target uuid, require_scope boolean default true)
returns boolean language sql stable security definer set search_path = '' as $$
  select (not require_scope or target = vouch_private.organization_id())
    and exists (
      select 1 from vouch.users u join vouch.memberships m on m.user_id = u.id
      where u.auth_subject = vouch_private.subject_id()
        and (vouch_private.user_id() is null or u.id = vouch_private.user_id())
        and m.organization_id = target and m.active
    )
$$;
create function vouch_private.has_role(target uuid, allowed text[])
returns boolean language sql stable security definer set search_path = '' as $$
  select vouch_private.member_of(target) and exists (
    select 1 from vouch.users u
    join vouch.memberships m on m.user_id = u.id
    join vouch.membership_roles r on r.membership_id = m.id
      and r.organization_id = m.organization_id
    where u.auth_subject = vouch_private.subject_id() and u.id = vouch_private.user_id()
      and m.organization_id = target and m.active and r.role = any(allowed)
  )
$$;
create function vouch_private.own_membership(target uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from vouch.memberships m join vouch.users u on u.id = m.user_id
    where m.id = target and m.active and u.auth_subject = vouch_private.subject_id()
      and (vouch_private.user_id() is null or u.id = vouch_private.user_id())
  )
$$;
create function vouch_private.analysis_deleted(target uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from vouch.analyses a
    join vouch.submission_versions sv on sv.id = a.submission_version_id
      and sv.organization_id = a.organization_id
    join vouch.submissions s on s.id = sv.submission_id
      and s.organization_id = a.organization_id
    join vouch.media_assets ma on ma.id = sv.asset_id
      and ma.organization_id = a.organization_id
    where a.id = target and a.organization_id = vouch_private.organization_id()
      and (ma.deleted_at is not null or ma.status = 'deleted' or s.deleted_at is not null
        or exists (select 1 from vouch.tombstones t
          where t.organization_id = a.organization_id
            and ((t.resource_type = 'submission' and t.resource_id = s.id)
              or (t.resource_type = 'media_asset' and t.resource_id = ma.id))))
  )
$$;
revoke all on all functions in schema vouch_private from public, anon, authenticated;
grant execute on all functions in schema vouch_private to vouch_api, vouch_worker;

grant select on all tables in schema vouch to vouch_api;
create policy api_identity on vouch.users for select to vouch_api
  using (auth_subject = (select vouch_private.subject_id()));
create policy api_memberships on vouch.memberships for select to vouch_api
  using (vouch_private.own_membership(id));
create policy api_membership_roles on vouch.membership_roles for select to vouch_api
  using (vouch_private.own_membership(membership_id));
create policy api_organizations on vouch.organizations for select to vouch_api
  using (vouch_private.member_of(id, false));

-- All domain reads require both a selected organization and its current active membership.
do $$ declare relation text; extra text; begin
  foreach relation in array array[
    'brands','products','creators','rule_pack_versions','campaigns','campaign_creators',
    'media_assets','submissions','submission_versions','analyses','jobs','budget_reservations',
    'idempotency_records','evidence_items','findings','review_contexts','finding_decisions',
    'review_events','approvals','fix_request_drafts','audit_events','tombstones','deletion_requests'
  ] loop
    execute format('create policy api_read on vouch.%I for select to vouch_api using (vouch_private.member_of(organization_id))', relation);
  end loop;
end $$;

-- Domain catalog, subjects, memberships, roles and rulebooks remain provisioning-owned.
grant insert on vouch.campaigns, vouch.campaign_creators, vouch.media_assets,
  vouch.submissions, vouch.submission_versions, vouch.analyses, vouch.jobs,
  vouch.budget_reservations, vouch.idempotency_records, vouch.finding_decisions,
  vouch.review_events, vouch.approvals, vouch.fix_request_drafts, vouch.audit_events,
  vouch.tombstones, vouch.deletion_requests to vouch_api;
grant update (budget_held_minor) on vouch.organizations to vouch_api;
grant update (filename, validated_content_type, actual_bytes, sha256, duration_ms,
  status, object_bytes, deleted_at) on vouch.media_assets to vouch_api;
grant update (current_version_id, deleted_at) on vouch.submissions to vouch_api;
grant update (caption) on vouch.submission_versions to vouch_api;
grant update (job_id, analysis_status, machine_assessment, observed_coverage,
  missing_intervals, completed_at) on vouch.analyses to vouch_api;
grant update (status, fence, lease_owner, lease_until, retry_after, updated_at)
  on vouch.jobs to vouch_api;
grant update (status, reconciled_at) on vouch.budget_reservations to vouch_api;
grant update (revision, review_status, superseded_at) on vouch.review_contexts to vouch_api;
grant update (description) on vouch.evidence_items to vouch_api;
grant update (evidence_text, uncertainty, suggested_action) on vouch.findings to vouch_api;
grant update (rationale) on vouch.finding_decisions, vouch.review_events to vouch_api;
grant update (text) on vouch.fix_request_drafts to vouch_api;
grant update (status, destinations, completed_at) on vouch.deletion_requests to vouch_api;

create policy api_budget_update on vouch.organizations for update to vouch_api
  using (vouch_private.has_role(id, array['admin','marketer']))
  with check (vouch_private.has_role(id, array['admin','marketer']));
do $$ declare relation text; extra text; begin
  foreach relation in array array[
    'campaigns','campaign_creators','media_assets','submissions','submission_versions',
    'analyses','jobs','budget_reservations','idempotency_records','fix_request_drafts',
    'tombstones','deletion_requests'
  ] loop
    extra := case relation
      when 'analyses' then ' and analysis_status = ''queued'' and machine_assessment = ''not_assessed'' and observed_coverage::jsonb = ''[]''::jsonb and missing_intervals::jsonb = ''[]''::jsonb and completed_at is null'
      when 'jobs' then ' and status = ''queued'' and attempt_count = 0 and fence = 0 and result_id is null'
      when 'media_assets' then ' and status = ''intent_created'' and uploader_user_id = vouch_private.user_id() and rights_attested and object_bytes is null'
      when 'campaigns' then ' and created_by = vouch_private.user_id()'
      when 'submission_versions' then ' and uploader_user_id = vouch_private.user_id() and rights_attested'
      when 'idempotency_records' then ' and actor_user_id = vouch_private.user_id()'
      when 'fix_request_drafts' then ' and created_by = vouch_private.user_id()'
      when 'deletion_requests' then ' and requested_by = vouch_private.user_id()'
      else '' end;
    execute format('create policy api_insert on vouch.%I for insert to vouch_api with check (vouch_private.has_role(organization_id, array[''admin'',''marketer''])%s)', relation, extra);
  end loop;
  foreach relation in array array[
    'media_assets','submissions','jobs','budget_reservations','deletion_requests'
  ] loop
    execute format('create policy api_update on vouch.%I for update to vouch_api using (vouch_private.has_role(organization_id, array[''admin'',''marketer''])) with check (vouch_private.has_role(organization_id, array[''admin'',''marketer'']))', relation);
  end loop;
end $$;
create policy api_version_redaction on vouch.submission_versions for update to vouch_api
  using (vouch_private.has_role(organization_id, array['admin','marketer']))
  with check (vouch_private.has_role(organization_id, array['admin','marketer']) and caption = '');
create policy api_analysis_update on vouch.analyses for update to vouch_api
  using (vouch_private.has_role(organization_id, array['admin','marketer']))
  with check (vouch_private.has_role(organization_id, array['admin','marketer']));
create policy api_evidence_redaction on vouch.evidence_items for update to vouch_api
  using (vouch_private.has_role(organization_id, array['admin','marketer']))
  with check (vouch_private.has_role(organization_id, array['admin','marketer'])
    and description = '' and vouch_private.analysis_deleted(analysis_id));
create policy api_findings_redaction on vouch.findings for update to vouch_api
  using (vouch_private.has_role(organization_id, array['admin','marketer']))
  with check (vouch_private.has_role(organization_id, array['admin','marketer'])
    and evidence_text = '' and uncertainty = '' and suggested_action = ''
    and vouch_private.analysis_deleted(analysis_id));
create policy api_review_context_update on vouch.review_contexts for update to vouch_api
  using (vouch_private.has_role(organization_id, array['admin','marketer','reviewer']))
  with check (vouch_private.has_role(organization_id, array['reviewer'])
    or (vouch_private.has_role(organization_id, array['admin','marketer'])
      and review_status in ('unreviewed','superseded','revoked')));
do $$ declare relation text; begin
  foreach relation in array array['finding_decisions','review_events','approvals'] loop
    execute format('create policy api_human_insert on vouch.%I for insert to vouch_api with check (vouch_private.has_role(organization_id, array[''reviewer'']) and actor_user_id = vouch_private.user_id())', relation);
  end loop;
  foreach relation in array array['finding_decisions','review_events'] loop
    execute format('create policy api_rationale_redaction on vouch.%I for update to vouch_api using (vouch_private.has_role(organization_id, array[''admin'',''marketer''])) with check (vouch_private.has_role(organization_id, array[''admin'',''marketer'']) and rationale = '''')', relation);
  end loop;
end $$;
create policy api_draft_redaction on vouch.fix_request_drafts for update to vouch_api
  using (vouch_private.has_role(organization_id, array['admin','marketer']))
  with check (vouch_private.has_role(organization_id, array['admin','marketer'])
    and text = '' and vouch_private.analysis_deleted(analysis_id));
create policy api_audit_insert on vouch.audit_events for insert to vouch_api
  with check (vouch_private.member_of(organization_id) and actor_kind = 'member'
    and actor_user_id = vouch_private.user_id());

-- UPDATE grants needed for deletion must not let the API manufacture a machine result.
create function vouch_private.guard_api_analysis_update() returns trigger
language plpgsql set search_path = '' as $$
begin
  if current_user = 'vouch_api' or (pg_has_role(current_user, 'vouch_api', 'member')
    and not exists (select 1 from pg_catalog.pg_roles where rolname = current_user and rolsuper)) then
    if to_jsonb(new) - 'job_id' = to_jsonb(old) - 'job_id'
      and old.analysis_status = 'queued' and old.machine_assessment = 'not_assessed' then
      return new;
    end if;
    if vouch_private.analysis_deleted(new.id) and new.machine_assessment = 'not_assessed'
      and new.observed_coverage::jsonb = '[]'::jsonb and new.missing_intervals::jsonb = '[]'::jsonb
      and to_jsonb(new) - array['analysis_status','machine_assessment','observed_coverage','missing_intervals','completed_at']
        = to_jsonb(old) - array['analysis_status','machine_assessment','observed_coverage','missing_intervals','completed_at']
      and (new.analysis_status = old.analysis_status
        or (old.analysis_status in ('queued','running') and new.analysis_status = 'cancelled')) then
      return new;
    end if;
    raise insufficient_privilege using message = 'API cannot publish or alter machine results';
  end if;
  return new;
end $$;
revoke all on function vouch_private.guard_api_analysis_update() from public, anon, authenticated;
create trigger guard_api_analysis_update before update on vouch.analyses
  for each row execute function vouch_private.guard_api_analysis_update();

-- Worker discovers jobs globally, then sets tenant context from the stored job before any
-- source/result query. No grants exist for identities, rules, human decisions or approvals.
grant select on vouch.jobs to vouch_worker;
grant update (status, attempt_count, retry_after, lease_owner, lease_until, fence,
  last_error_code, last_error_message, result_id, updated_at) on vouch.jobs to vouch_worker;
create policy worker_job_read on vouch.jobs for select to vouch_worker using (true);
create policy worker_job_update on vouch.jobs for update to vouch_worker using (true) with check (true);
grant select on vouch.organizations, vouch.campaigns, vouch.rule_pack_versions,
  vouch.media_assets, vouch.submissions, vouch.submission_versions, vouch.analyses,
  vouch.budget_reservations, vouch.tombstones, vouch.evidence_items, vouch.findings,
  vouch.review_contexts, vouch.audit_events to vouch_worker;
grant update (budget_held_minor) on vouch.organizations to vouch_worker;
grant update (analysis_status, machine_assessment, observed_coverage, missing_intervals,
  completed_at) on vouch.analyses to vouch_worker;
grant update (status, reconciled_at) on vouch.budget_reservations to vouch_worker;
-- SELECT FOR UPDATE of the submission is the publication/deletion concurrency lock.
grant update (current_version_id) on vouch.submissions to vouch_worker;
grant insert on vouch.evidence_items, vouch.findings, vouch.review_contexts,
  vouch.audit_events to vouch_worker;
do $$ declare relation text; begin
  foreach relation in array array[
    'organizations','campaigns','rule_pack_versions','media_assets','submissions',
    'submission_versions','analyses','budget_reservations','tombstones','evidence_items',
    'findings','review_contexts','audit_events'
  ] loop
    execute format('create policy worker_read on vouch.%I for select to vouch_worker using (%I = (select vouch_private.organization_id()))', relation, case when relation = 'organizations' then 'id' else 'organization_id' end);
  end loop;
  foreach relation in array array['organizations','submissions','analyses','budget_reservations'] loop
    execute format('create policy worker_update on vouch.%I for update to vouch_worker using (%I = (select vouch_private.organization_id())) with check (%I = (select vouch_private.organization_id()))', relation, case when relation = 'organizations' then 'id' else 'organization_id' end, case when relation = 'organizations' then 'id' else 'organization_id' end);
  end loop;
  foreach relation in array array['evidence_items','findings'] loop
    execute format('create policy worker_insert on vouch.%I for insert to vouch_worker with check (organization_id = (select vouch_private.organization_id()))', relation);
  end loop;
end $$;
create policy worker_review_context_insert on vouch.review_contexts for insert to vouch_worker
  with check (organization_id = (select vouch_private.organization_id())
    and review_status in ('unreviewed','superseded') and revision = 1);
create policy worker_audit_insert on vouch.audit_events for insert to vouch_worker
  with check (organization_id = (select vouch_private.organization_id())
    and actor_kind = 'worker' and actor_user_id is null);

create function vouch_private.guard_worker_submission_update() returns trigger
language plpgsql set search_path = '' as $$
begin
  if (current_user = 'vouch_worker' or (pg_has_role(current_user, 'vouch_worker', 'member')
    and not exists (select 1 from pg_catalog.pg_roles where rolname = current_user and rolsuper)))
    and new is distinct from old then
    raise insufficient_privilege using message = 'Worker may lock but not change submissions';
  end if;
  return new;
end $$;
revoke all on function vouch_private.guard_worker_submission_update() from public, anon, authenticated;
create trigger guard_worker_submission_update before update on vouch.submissions
  for each row execute function vouch_private.guard_worker_submission_update();

-- No object overwrite: upload retry must reconcile the existing bytes. Client deletion is
-- intentionally denied; only server cleanup can close a durable deletion receipt.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('vouch-media', 'vouch-media', false, 5000000, array['video/mp4','video/webm']);
create function vouch_private.storage_access(object_name text, writing boolean)
returns boolean language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and exists (
    select 1 from vouch.media_assets ma
    join vouch.campaigns c on c.id = ma.campaign_id and c.organization_id = ma.organization_id
    join vouch.memberships m on m.organization_id = ma.organization_id and m.active
    join vouch.users u on u.id = m.user_id and u.auth_subject = auth.uid()
    where ma.storage_backend = 'supabase' and ma.object_key = object_name
      and object_name = ma.organization_id::text || '/' || ma.campaign_id::text || '/' || ma.id::text || '/source'
      and ma.rights_attested and ma.deleted_at is null and ma.retention_deadline > now()
      and not exists (select 1 from vouch.tombstones t
        where t.organization_id = ma.organization_id and t.resource_type = 'media_asset'
          and t.resource_id = ma.id)
      and not exists (select 1 from vouch.submission_versions sv
        join vouch.submissions s on s.id = sv.submission_id and s.organization_id = sv.organization_id
        where sv.asset_id = ma.id and sv.organization_id = ma.organization_id
          and (s.deleted_at is not null or exists (select 1 from vouch.tombstones t
            where t.organization_id = s.organization_id and t.resource_type = 'submission'
              and t.resource_id = s.id)))
      and (
        (not writing and ma.status = 'validated')
        or (ma.status in ('intent_created','content_uploaded')
          and ma.created_at > now() - interval '5 minutes' and ma.uploader_user_id = u.id
          and exists (select 1 from vouch.membership_roles r
            where r.membership_id = m.id and r.organization_id = m.organization_id
              and r.role in ('admin','marketer')))
      )
  )
$$;
revoke all on function vouch_private.storage_access(text, boolean) from public, anon;
grant execute on function vouch_private.storage_access(text, boolean) to authenticated;
create policy vouch_media_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'vouch-media' and vouch_private.storage_access(name, true));
create policy vouch_media_read on storage.objects for select to authenticated
  using (bucket_id = 'vouch-media' and vouch_private.storage_access(name, false));
