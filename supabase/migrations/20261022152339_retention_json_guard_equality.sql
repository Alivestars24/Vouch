-- PostgreSQL json has no equality operator; compare complete records as jsonb.
-- Keep this additive because the preceding policy migration was already exercised locally.
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
    else valid := false;
  end case;
  if not coalesce(valid,false) then
    raise insufficient_privilege using message='Retention may only scrub anchored expired content';
  end if;
  return new;
end $$;
create or replace function vouch_private.guard_deletion_receipt_update() returns trigger
language plpgsql set search_path = '' as $$
declare old_targets jsonb; new_targets jsonb;
begin
  if exists (select 1 from pg_catalog.pg_roles where rolname=current_user
    and (rolsuper or rolbypassrls)) then return new; end if;
  if to_jsonb(new)=to_jsonb(old) then return new; end if;
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

-- Match the application's claim-index contract, without retaining two overlapping indexes.
create index ix_deletion_request_claim on vouch.deletion_requests (status,retry_after,lease_until);
drop index vouch.ix_deletion_claim;
