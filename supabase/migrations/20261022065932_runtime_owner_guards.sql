-- Supabase's migration owner is BYPASSRLS but not SUPERUSER. Runtime guards must not
-- accidentally treat that provisioning role as its restricted inherited application role.
create or replace function vouch_private.guard_api_analysis_update() returns trigger
language plpgsql set search_path = '' as $$
begin
  if current_user = 'vouch_api' or (pg_has_role(current_user, 'vouch_api', 'member')
    and not exists (select 1 from pg_catalog.pg_roles where rolname = current_user
      and (rolsuper or rolbypassrls))) then
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
create or replace function vouch_private.guard_worker_submission_update() returns trigger
language plpgsql set search_path = '' as $$
begin
  if (current_user = 'vouch_worker' or (pg_has_role(current_user, 'vouch_worker', 'member')
    and not exists (select 1 from pg_catalog.pg_roles where rolname = current_user
      and (rolsuper or rolbypassrls)))) and new is distinct from old then
    raise insufficient_privilege using message = 'Worker may lock but not change submissions';
  end if;
  return new;
end $$;
