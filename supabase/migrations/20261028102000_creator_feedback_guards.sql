-- Close publication and erasure gaps discovered while exercising the API service
-- against the restricted runtime roles. Keep the original publication migration
-- immutable because it has already been applied locally.

create or replace function vouch_private.creator_feedback_publishable(
  tenant uuid,
  target_submission uuid,
  target_version uuid,
  target_analysis uuid,
  target_draft uuid,
  snapshot_manifest_hash text,
  snapshot_invocation_mode text,
  snapshot_analysis_status text,
  range_start_ms integer,
  range_end_ms integer
) returns boolean
language sql security definer set search_path = '' as $$
  select exists (
    select 1
    from vouch.submissions s
    join vouch.submission_versions sv
      on sv.organization_id = s.organization_id
      and sv.submission_id = s.id
      and sv.id = target_version
    join vouch.media_assets ma
      on ma.organization_id = sv.organization_id and ma.id = sv.asset_id
    join vouch.analyses a
      on a.organization_id = sv.organization_id
      and a.submission_version_id = sv.id
      and a.id = target_analysis
    join vouch.review_contexts rc
      on rc.organization_id = a.organization_id
      and rc.analysis_id = a.id
      and rc.submission_id = s.id
      and rc.submission_version_id = sv.id
    join vouch.fix_request_drafts d
      on d.organization_id = a.organization_id
      and d.analysis_id = a.id
      and d.id = target_draft
    where s.organization_id = tenant
      and s.id = target_submission
      and s.current_version_id = sv.id
      and s.deleted_at is null
      and ma.deleted_at is null
      and ma.status = 'validated'
      and ma.retention_deadline > clock_timestamp()
      and exists (
        select 1
        from vouch.consent_receipts cr
        where cr.organization_id = ma.organization_id
          and cr.asset_id = ma.id
          and cr.purpose = 'campaign_check'
          and cr.revoked_at is null
      )
      and d.text <> ''
      and rc.review_status <> 'superseded'
      and rc.superseded_at is null
      and a.analysis_status in ('completed', 'partial')
      and a.manifest_hash = snapshot_manifest_hash
      and a.invocation_mode = snapshot_invocation_mode
      and a.analysis_status = snapshot_analysis_status
      and (
        (range_start_ms is null and range_end_ms is null)
        or (
          range_start_ms is not null and range_end_ms is not null
          and range_start_ms >= 0 and range_end_ms > range_start_ms
          and ma.duration_ms is not null and range_end_ms <= ma.duration_ms
        )
      )
      and not exists (
        select 1 from vouch.tombstones t
        where t.organization_id = tenant
          and (
            (t.resource_type = 'submission' and t.resource_id = s.id)
            or (t.resource_type = 'media_asset' and t.resource_id = ma.id)
          )
      )
  )
$$;

create function vouch_private.creator_feedback_scrubbable(
  tenant uuid,
  target_analysis uuid
) returns boolean
language sql security definer set search_path = '' as $$
  select exists (
    select 1
    from vouch.analyses a
    join vouch.submission_versions sv
      on sv.organization_id = a.organization_id
      and sv.id = a.submission_version_id
    join vouch.submissions s
      on s.organization_id = sv.organization_id
      and s.id = sv.submission_id
    join vouch.media_assets ma
      on ma.organization_id = sv.organization_id
      and ma.id = sv.asset_id
    where a.organization_id = tenant
      and a.id = target_analysis
      and (
        s.deleted_at is not null
        or ma.deleted_at is not null
        or exists (
          select 1 from vouch.tombstones t
          where t.organization_id = tenant
            and (
              (t.resource_type = 'submission' and t.resource_id = s.id)
              or (t.resource_type = 'media_asset' and t.resource_id = ma.id)
            )
        )
      )
  )
$$;
revoke all on function vouch_private.creator_feedback_scrubbable(uuid, uuid)
  from public, anon, authenticated, vouch_worker, vouch_guest, vouch_retention;
grant execute on function vouch_private.creator_feedback_scrubbable(uuid, uuid)
  to vouch_api;

grant update(message, start_ms, end_ms) on vouch.creator_feedback to vouch_api;
create policy api_creator_feedback_scrub
  on vouch.creator_feedback for update to vouch_api
  using (
    vouch_private.has_role(organization_id, array['admin', 'marketer'])
  )
  with check (
    vouch_private.has_role(organization_id, array['admin', 'marketer'])
    and message = '' and start_ms is null and end_ms is null
    and vouch_private.creator_feedback_scrubbable(organization_id, analysis_id)
  );

create function vouch_private.guard_api_creator_feedback_scrub() returns trigger
language plpgsql set search_path = '' as $$
declare valid boolean := false;
begin
  if not (
    current_user = 'vouch_api'
    or (
      pg_has_role(current_user, 'vouch_api', 'member')
      and not exists (
        select 1 from pg_catalog.pg_roles
        where rolname = current_user and (rolsuper or rolbypassrls)
      )
    )
  ) then return new; end if;
  valid := new.message = '' and new.start_ms is null and new.end_ms is null
    and to_jsonb(new) - array['message', 'start_ms', 'end_ms']
      = to_jsonb(old) - array['message', 'start_ms', 'end_ms']
    and vouch_private.creator_feedback_scrubbable(
      new.organization_id, new.analysis_id
    );
  if not coalesce(valid, false) then
    raise insufficient_privilege using
      message = 'API may only scrub feedback for a deleted exact source';
  end if;
  return new;
end
$$;
revoke all on function vouch_private.guard_api_creator_feedback_scrub()
  from public, anon, authenticated, vouch_worker, vouch_guest, vouch_retention;
create trigger guard_api_creator_feedback_scrub
  before update on vouch.creator_feedback
  for each row execute function vouch_private.guard_api_creator_feedback_scrub();

grant update(message, start_ms, end_ms) on vouch.creator_feedback to vouch_retention;
create or replace function vouch_private.guard_retention_scrub() returns trigger
language plpgsql set search_path = '' as $$
declare valid boolean := false;
begin
  if not (current_user='vouch_retention' or (pg_has_role(current_user,'vouch_retention','member')
    and not exists (select 1 from pg_catalog.pg_roles where rolname=current_user
      and (rolsuper or rolbypassrls)))) then return new; end if;
  if to_jsonb(new)=to_jsonb(old) then return new; end if;
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
    when 'creator_feedback' then valid := new.message=''
      and new.start_ms is null and new.end_ms is null
      and to_jsonb(new)-array['message','start_ms','end_ms']
        =to_jsonb(old)-array['message','start_ms','end_ms'];
    else valid := false;
  end case;
  if not coalesce(valid,false) then
    raise insufficient_privilege using message='Retention may only scrub anchored expired content';
  end if;
  return new;
end
$$;
